"""Reproducible benchmark runner.

Iterates over `examples/<task_type>/<slug>/` directories. For each pair:
  1. Compress `verbose.md` via denser (Opus 4.6)
  2. Evaluate both original and compressed via the eval harness (Haiku 4.5 judge)
  3. Record savings + pass-rate delta

Results aggregate per task type and are printed to stdout (or written to JSON).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Ensure denser is importable when running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from denser import compare, compress  # noqa: E402
from denser.backends import BackendError, ClaudeBackend  # noqa: E402
from denser.taxonomy import TaskType  # noqa: E402

logger = logging.getLogger("denser.benchmarks")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")


@dataclass
class PairResult:
    task_type: str
    slug: str
    original_tokens: int
    compressed_tokens: int
    savings_pct: float
    pass_rate_original: float
    pass_rate_compressed: float
    delta: float


def _examples_root() -> Path:
    return Path(__file__).resolve().parent.parent / "examples"


def _discover_pairs(task_type_filter: str | None) -> list[tuple[TaskType, Path]]:
    """Find every `examples/<task_type>/<slug>/verbose.md` pair."""
    pairs: list[tuple[TaskType, Path]] = []
    root = _examples_root()
    for type_dir in sorted(root.iterdir()):
        if not type_dir.is_dir():
            continue
        # Directory names use plural; taxonomy uses singular. Try both.
        raw_name = type_dir.name.rstrip("s")
        try:
            tt = TaskType.parse(raw_name)
        except ValueError:
            try:
                tt = TaskType.parse(type_dir.name)
            except ValueError:
                continue
        if task_type_filter and tt.value != task_type_filter:
            continue
        for slug_dir in sorted(type_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            verbose = slug_dir / "verbose.md"
            if verbose.is_file():
                pairs.append((tt, slug_dir))
    return pairs


def run_pair(
    tt: TaskType,
    slug_dir: Path,
    *,
    compressor: ClaudeBackend,
    judge: ClaudeBackend,
    n_trials: int,
) -> PairResult:
    verbose = (slug_dir / "verbose.md").read_text(encoding="utf-8")

    logger.info("Compressing %s/%s ...", tt.value, slug_dir.name)
    result = compress(verbose, task_type=tt, backend=compressor)

    # Save the freshly-compressed output alongside the hand-curated dense.md
    out_path = slug_dir / "bench_compressed.md"
    out_path.write_text(result.compressed, encoding="utf-8")

    logger.info("Evaluating %s/%s ...", tt.value, slug_dir.name)
    cmp = compare(
        original=verbose,
        compressed=result.compressed,
        task_type=tt,
        judge_backend=judge,
        n_trials=n_trials,
    )

    return PairResult(
        task_type=tt.value,
        slug=slug_dir.name,
        original_tokens=result.original_tokens,
        compressed_tokens=result.compressed_tokens,
        savings_pct=result.savings_pct,
        pass_rate_original=cmp.original.overall_pass_rate,
        pass_rate_compressed=cmp.compressed.overall_pass_rate,
        delta=cmp.delta,
    )


def aggregate(results: list[PairResult]) -> dict[str, dict[str, float | int]]:
    by_type: dict[str, list[PairResult]] = {}
    for r in results:
        by_type.setdefault(r.task_type, []).append(r)

    agg: dict[str, dict[str, float | int]] = {}
    for tt, rs in by_type.items():
        agg[tt] = {
            "n_samples": len(rs),
            "avg_savings_pct": statistics.fmean(r.savings_pct for r in rs),
            "avg_delta": statistics.fmean(r.delta for r in rs),
            "worst_delta": min(r.delta for r in rs),
            "avg_pass_rate_original": statistics.fmean(r.pass_rate_original for r in rs),
            "avg_pass_rate_compressed": statistics.fmean(r.pass_rate_compressed for r in rs),
        }
    return agg


def print_summary(results: list[PairResult], agg: dict) -> None:
    print("\n" + "=" * 78)
    print(" Per-pair results")
    print("=" * 78)
    print(f"{'task_type':<18} {'slug':<30} {'orig→comp':<14} {'save':<7} {'Δ':<8}")
    print("-" * 78)
    for r in sorted(results, key=lambda x: (x.task_type, x.slug)):
        print(
            f"{r.task_type:<18} {r.slug:<30} "
            f"{r.original_tokens:>4}→{r.compressed_tokens:<4}  "
            f"{r.savings_pct:>5.0%}  "
            f"{r.delta:+.2%}"
        )

    print("\n" + "=" * 78)
    print(" Aggregated by task type")
    print("=" * 78)
    print(f"{'task_type':<18} {'N':<4} {'avg save':<10} {'avg Δ':<10} {'worst Δ':<10}")
    print("-" * 78)
    for tt, a in sorted(agg.items()):
        print(
            f"{tt:<18} {a['n_samples']:<4} "
            f"{a['avg_savings_pct']:>7.0%}   "
            f"{a['avg_delta']:+7.2%}   "
            f"{a['worst_delta']:+7.2%}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run denser benchmarks.")
    parser.add_argument(
        "--type",
        default=None,
        help="Only run pairs of this task type. Omit for all.",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=1,
        help="Eval trials per test case (higher = less judge noise). Default: 1.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write full results as JSON to this path.",
    )
    parser.add_argument(
        "--model",
        default="claude-opus-4-6",
        help="Compressor model (default: claude-opus-4-6).",
    )
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Judge model (default: claude-haiku-4-5).",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — benchmarks require live API access.", file=sys.stderr)
        return 2

    try:
        compressor = ClaudeBackend(model=args.model)
        judge = ClaudeBackend(model=args.judge_model, temperature=0.0)
    except BackendError as e:
        print(f"Backend error: {e}", file=sys.stderr)
        return 2

    pairs = _discover_pairs(args.type)
    if not pairs:
        print(f"No example pairs found" + (f" for type {args.type!r}" if args.type else ""))
        return 1

    logger.info("Discovered %d pairs", len(pairs))

    results: list[PairResult] = []
    for tt, slug_dir in pairs:
        try:
            results.append(
                run_pair(
                    tt,
                    slug_dir,
                    compressor=compressor,
                    judge=judge,
                    n_trials=args.n_trials,
                )
            )
        except Exception as e:
            logger.exception("Failed on %s/%s: %s", tt.value, slug_dir.name, e)

    agg = aggregate(results)

    print_summary(results, agg)

    if args.out:
        args.out.write_text(
            json.dumps(
                {
                    "results": [asdict(r) for r in results],
                    "aggregate": agg,
                    "settings": {
                        "model": args.model,
                        "judge_model": args.judge_model,
                        "n_trials": args.n_trials,
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote results to {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
