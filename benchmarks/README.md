# denser benchmarks

Reproducible benchmark suite for the signal density curve framework.

## What it does

1. Iterates over all curated example pairs in `examples/`
2. For each pair:
   - Compresses the `verbose.md` using denser + Claude Opus 4.6
   - Evaluates both `verbose.md` (original) and the compressed output on that task type's golden tasks
   - Reports pass-rate delta + token savings
3. Aggregates per-task-type statistics for the README table

## Requirements

- `ANTHROPIC_API_KEY` environment variable set
- `pip install -e ".[dev]"` from repo root

## Run

```bash
python benchmarks/run.py                    # all task types
python benchmarks/run.py --type skill       # one task type
python benchmarks/run.py --n-trials 30      # production-grade judge noise mitigation
python benchmarks/run.py --out results.json # persist results
```

## Expected wall time

- `--n-trials 1` (CI smoke): ~2-5 minutes for the full corpus
- `--n-trials 30` (production): ~30-90 minutes for the full corpus

## Cost

Rough API bill per run at default `--n-trials 1`:
- Compression (Opus 4.6): $0.01-0.05 per example
- Evaluation (Haiku 4.5): < $0.001 per example

Per-run total: typically < $1 at v0.1 corpus size.

## What to look for

A healthy benchmark run produces:
- **Avg savings** ≥ 40% across task types (compression is doing real work)
- **Pass-rate delta** within ±3% of zero (compression preserves task performance)
- **No example** with delta < -10% (no catastrophic compression failures)

Anomalies — significantly negative deltas on a specific pair — are the most valuable signal. They indicate the compression strategy for that task type is under-specified or the input has unusual structure.

## Contributing benchmark results

If you run this on your own examples, we welcome PRs adding them to `examples/`. See `docs/CONTRIBUTING.md` §"Submitting a sample pair".
