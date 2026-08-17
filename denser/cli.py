"""Command-line interface.

Entry point registered via pyproject.toml as `denser`.

Commands:
- `denser audit` — audit behavior parity and replay-suite sensitivity
- `denser inspect` — build an offline preservation contract
- `denser verify` — verify a candidate against its source contract
- `denser optimize` — generate and select verified candidates
- `denser compress` — compress a single file
- `denser info` — show the taxonomy summary (offline, no API calls)
- `denser eval` — run observed structural or caller-supplied checks
- `denser replay` — execute deterministic, asset-specific behavior cases
- `denser curve` — run an experimental density sweep
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from denser import __version__
from denser.audit import AuditDecision, ContextAuditReport
from denser.audit import audit_context as audit_context_fn
from denser.backends import (
    CODEX_CAPABILITY_PROFILES,
    Backend,
    BackendError,
    ClaudeBackend,
    CodexCliBackend,
    OpenAICompatibleBackend,
    SiliconFlowBackend,
)
from denser.compress import compress
from denser.curve import curve as curve_fn
from denser.eval import ComparisonReport, EvalReport
from denser.eval import compare as compare_fn
from denser.eval import evaluate as evaluate_fn
from denser.inspection import InspectionAction
from denser.inspection import inspect as inspect_fn
from denser.optimization import OptimizationReport
from denser.optimization import optimize as optimize_fn
from denser.replay import ReplayComparisonReport, ReplayProgress, ReplayReport, load_replay_suite
from denser.replay import compare_replay as compare_replay_fn
from denser.replay import replay as replay_fn
from denser.taxonomy import SPECS, TaskType
from denser.verification import VerificationDecision
from denser.verification import verify as verify_fn

BACKEND_CHOICES = ["claude", "siliconflow", "openai-compat"]
REPLAY_BACKEND_CHOICES = [*BACKEND_CHOICES, "codex-cli"]


def _build_backend(
    kind: str,
    *,
    model: str | None,
    base_url: str | None,
    temperature: float = 0.3,
    codex_cli_path: Path | None = None,
    codex_timeout: float = 180.0,
    codex_reasoning_effort: str = "medium",
    codex_respect_system_proxy: bool = False,
    openai_thinking_mode: str = "provider-default",
    codex_capability_profile: str = "standard",
) -> Backend:
    """Construct a backend from CLI arguments."""
    if kind == "claude":
        return ClaudeBackend(model=model or "claude-opus-4-6", temperature=temperature)
    if kind == "siliconflow":
        return SiliconFlowBackend(model=model or "deepseek-ai/DeepSeek-V3", temperature=temperature)
    if kind == "openai-compat":
        if not base_url:
            raise BackendError(
                "--base-url is required for openai-compat backend (e.g. https://api.openai.com/v1)"
            )
        if not model:
            raise BackendError("--model is required for openai-compat backend")
        return OpenAICompatibleBackend(
            base_url=base_url,
            model=model,
            temperature=temperature,
            thinking_mode=openai_thinking_mode,
        )
    if kind == "codex-cli":
        return CodexCliBackend(
            executable=codex_cli_path,
            model=model or "gpt-5.6-sol",
            reasoning_effort=codex_reasoning_effort,
            timeout_seconds=codex_timeout,
            respect_system_proxy=codex_respect_system_proxy,
            capability_profile=codex_capability_profile,
        )
    raise BackendError(f"Unknown backend: {kind}")


console = Console()


def _make_console_output_loss_tolerant() -> None:
    """Avoid Windows code-page crashes while preserving source data in reports."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


@click.group()
@click.version_option(version=__version__, prog_name="denser")
def main() -> None:
    """denser: behavior-fidelity audits for LLM context changes."""
    _make_console_output_loss_tolerant()


@main.command("inspect")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
    help="Instruction profile used to classify preservation obligations.",
)
@click.option(
    "--min-tokens",
    type=click.IntRange(min=1),
    default=100,
    show_default=True,
    help="Below this estimate, recommend keeping the source unchanged.",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the complete inspection report as JSON.",
)
def inspect_cmd(
    input_file: Path,
    task_type: str,
    min_tokens: int,
    json_out: Path | None,
) -> None:
    """Build an offline preservation contract for INPUT_FILE."""
    text = input_file.read_text(encoding="utf-8")
    try:
        report = inspect_fn(
            text,
            task_type=task_type,
            source_name=str(input_file),
            min_tokens=min_tokens,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    summary = (
        f"Action: [bold]{report.action.value}[/bold]\n"
        f"Estimated tokens: {report.estimated_tokens}\n"
        f"Contract items: {len(report.contract.items)}\n"
        f"Uncovered high-risk items: {report.uncovered_high_risk_count}\n\n"
        "[green]No model or network calls were made.[/green]"
    )
    console.print(Panel.fit(summary, title="Offline inspection"))

    table = Table(title="Preservation contract", show_lines=False)
    table.add_column("ID", no_wrap=True)
    table.add_column("Categories")
    table.add_column("Risk", no_wrap=True)
    table.add_column("Lines", justify="right", no_wrap=True)
    table.add_column("Source-backed statement")
    for item in report.contract.items:
        categories = ",".join(category.value for category in item.categories)
        lines = str(item.source.start_line)
        if item.source.end_line != item.source.start_line:
            lines = f"{item.source.start_line}-{item.source.end_line}"
        table.add_row(
            item.item_id,
            categories,
            item.risk.value,
            lines,
            escape(item.statement),
        )
    console.print(table)

    if report.warnings:
        console.print("\n[bold]Review notes:[/bold]")
        for warning in report.warnings:
            console.print(f"- {escape(warning)}")

    if json_out is not None:
        json_out.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"\nWrote inspection JSON -> {json_out}")


@main.command("verify")
@click.argument("original_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("candidate_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
    help="Instruction profile used to build the preservation contract.",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the complete verification report as JSON.",
)
def verify_cmd(
    original_file: Path,
    candidate_file: Path,
    task_type: str,
    json_out: Path | None,
) -> None:
    """Verify CANDIDATE_FILE against ORIGINAL_FILE without model calls."""
    original = original_file.read_text(encoding="utf-8")
    candidate = candidate_file.read_text(encoding="utf-8")
    report = verify_fn(original, candidate, task_type=task_type)

    decision_style = {
        VerificationDecision.PASS: "green",
        VerificationDecision.REVIEW: "yellow",
        VerificationDecision.REJECT: "red",
    }[report.decision]
    summary = (
        f"Decision: [{decision_style}]{report.decision.value}[/{decision_style}]\n"
        f"Estimated tokens: {report.original_tokens} -> {report.candidate_tokens}\n"
        f"Estimated density: {report.actual_density:.3f}\n"
        f"Review items: {report.review_count}\n"
        f"Failed items: {report.failed_item_count}\n\n"
        "[green]No model or network calls were made.[/green]"
    )
    console.print(Panel.fit(summary, title="Candidate verification"))

    contract_by_id = {item.item_id: item for item in report.contract.items}
    table = Table(title="Contract coverage", show_lines=False)
    table.add_column("ID", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Lines", justify="right", no_wrap=True)
    table.add_column("Evidence")
    for result in report.item_results:
        item = contract_by_id[result.item_id]
        lines = str(item.source.start_line)
        if item.source.end_line != item.source.start_line:
            lines = f"{item.source.start_line}-{item.source.end_line}"
        table.add_row(
            result.item_id,
            result.status.value,
            lines,
            escape("; ".join(result.evidence)),
        )
    console.print(table)

    if report.failures:
        console.print("\n[bold red]Failures:[/bold red]")
        for failure in report.failures:
            console.print(f"- {escape(failure)}")
    if report.warnings:
        console.print("\n[bold]Review notes:[/bold]")
        for warning in report.warnings:
            console.print(f"- {escape(warning)}")

    if json_out is not None:
        json_out.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"\nWrote verification JSON -> {json_out}")

    exit_code = {
        VerificationDecision.PASS: 0,
        VerificationDecision.REVIEW: 3,
        VerificationDecision.REJECT: 2,
    }[report.decision]
    if exit_code:
        raise click.exceptions.Exit(exit_code)


@main.command("optimize")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
)
@click.option(
    "--densities",
    default=None,
    help="Comma-separated candidate densities. Default: low, midpoint, and high for the type.",
)
@click.option(
    "--backend",
    type=click.Choice(BACKEND_CHOICES, case_sensitive=False),
    default="claude",
    show_default=True,
)
@click.option("--base-url", default=None, help="Base URL for openai-compat backend.")
@click.option("--model", default=None, help="Model id; defaults depend on backend.")
@click.option(
    "--min-tokens",
    type=click.IntRange(min=1),
    default=100,
    show_default=True,
    help="Below this estimate, keep the original without model calls.",
)
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the recommended text to a new file.",
)
@click.option(
    "--evidence-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the versioned evidence report as JSON, including candidate text.",
)
def optimize_cmd(
    input_file: Path,
    task_type: str,
    densities: str | None,
    backend: str,
    base_url: str | None,
    model: str | None,
    min_tokens: int,
    out: Path | None,
    evidence_out: Path | None,
) -> None:
    """Generate candidates and recommend only the shortest verified option."""
    _validate_new_output_paths(input_file, out, evidence_out)
    requested_densities = _parse_density_values(densities)

    text = input_file.read_text(encoding="utf-8")
    preview = inspect_fn(
        text, task_type=task_type, source_name=str(input_file), min_tokens=min_tokens
    )
    backend_obj: Backend | None = None
    if preview.action != InspectionAction.KEEP:
        try:
            backend_obj = _build_backend(backend, model=model, base_url=base_url)
        except BackendError as exc:
            raise click.ClickException(str(exc)) from exc
    with console.status(
        f"Generating and verifying candidates for [cyan]{input_file.name}[/cyan]..."
    ):
        report = optimize_fn(
            text,
            task_type=task_type,
            backend=backend_obj,
            target_densities=requested_densities,
            min_tokens=min_tokens,
            source_name=str(input_file),
        )

    _print_optimization_report(report)
    _write_optimization_outputs(report, out, evidence_out)


def _validate_new_output_paths(
    input_file: Path,
    out: Path | None,
    evidence_out: Path | None,
) -> None:
    outputs = [path for path in (out, evidence_out) if path is not None]
    if any(path.resolve() == input_file.resolve() for path in outputs):
        raise click.ClickException("Refusing to overwrite the source file; choose a new path.")
    if out is not None and evidence_out is not None and out.resolve() == evidence_out.resolve():
        raise click.ClickException("--out and --evidence-out must be different files.")
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise click.ClickException(f"Refusing to overwrite existing output: {existing[0]}")
    missing_parents = [path.parent for path in outputs if not path.parent.exists()]
    if missing_parents:
        raise click.ClickException(f"Output directory does not exist: {missing_parents[0]}")


def _parse_density_values(densities: str | None) -> tuple[float, ...] | None:
    if densities is None:
        return None
    try:
        return tuple(float(value.strip()) for value in densities.split(",") if value.strip())
    except ValueError as exc:
        raise click.ClickException(f"Invalid --densities value: {densities!r}") from exc


def _print_optimization_report(report: OptimizationReport) -> None:
    table = Table(title="Optimization candidates", show_lines=False)
    table.add_column("Candidate")
    table.add_column("Target", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Decision")
    for candidate in report.candidates:
        target = (
            "-" if candidate.requested_density is None else f"{candidate.requested_density:.3f}"
        )
        tokens = "-" if candidate.token_count is None else str(candidate.token_count)
        if candidate.generation_error:
            decision = f"error:{candidate.generation_error}"
        elif candidate.measurement_error:
            decision = f"error:{candidate.measurement_error}"
        elif candidate.verification is not None:
            decision = candidate.verification.decision.value
        else:
            decision = "unverified"
        table.add_row(candidate.candidate_id, target, tokens, decision)
    console.print(table)
    console.print(
        Panel.fit(
            f"Recommended: [bold]{report.recommended_candidate_id}[/bold]\n"
            f"Changed: {str(report.changed).lower()}\n"
            f"Reason: {escape(report.recommendation_reason)}",
            title="Recommendation",
        )
    )


def _write_optimization_outputs(
    report: OptimizationReport,
    out: Path | None,
    evidence_out: Path | None,
) -> None:
    if out is not None:
        recommended_text = report.recommended.text
        if recommended_text is None:  # pragma: no cover - original is always available
            raise click.ClickException("Recommended candidate has no text")
        out.write_text(recommended_text, encoding="utf-8")
        console.print(f"Wrote recommended text -> {out}")
    if evidence_out is not None:
        evidence_out.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"Wrote evidence JSON -> {evidence_out}")


@main.command("compress")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
    help="Instruction profile (drives rewrite guidance and an exploratory target range).",
)
@click.option(
    "--density",
    type=float,
    default=None,
    help="Target density (compressed/original tokens). Default: taxonomy midpoint.",
)
@click.option(
    "--backend",
    type=click.Choice(BACKEND_CHOICES, case_sensitive=False),
    default="claude",
    show_default=True,
    help="Compression backend. `siliconflow` uses DeepSeek-V3 by default; "
    "`openai-compat` requires --base-url and --model.",
)
@click.option(
    "--base-url",
    default=None,
    help="Base URL for openai-compat backend (e.g. https://api.openai.com/v1).",
)
@click.option(
    "--model",
    default=None,
    help=(
        "Model id. Default depends on backend: claude-opus-4-6 (claude), "
        "deepseek-ai/DeepSeek-V3 (siliconflow). Required for openai-compat."
    ),
)
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output file. Defaults to `<input>.dense.<ext>`.",
)
@click.option(
    "--show-rationale/--no-show-rationale",
    default=True,
    help="Print the compressor's rationale to stderr.",
)
def compress_cmd(
    input_file: Path,
    task_type: str,
    density: float | None,
    backend: str,
    base_url: str | None,
    model: str | None,
    out: Path | None,
    show_rationale: bool,
) -> None:
    """Compress the contents of INPUT_FILE for a given task type."""
    if out is None:
        out = input_file.with_suffix(f".dense{input_file.suffix}")
    _validate_new_output_paths(input_file, out, None)
    text = input_file.read_text(encoding="utf-8")

    try:
        backend_obj = _build_backend(backend, model=model, base_url=base_url)
    except BackendError as e:
        console.print(f"[red]Backend error:[/red] {e}", style="bold")
        sys.exit(2)

    console.print(
        f"Compressing [bold]{input_file.name}[/bold] as [cyan]{task_type}[/cyan] "
        f"via [yellow]{backend_obj.name}[/yellow]..."
    )
    try:
        result = compress(text, task_type=task_type, target_density=density, backend=backend_obj)
    except (ValueError, BackendError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    out.write_text(result.compressed, encoding="utf-8")

    # Summary table
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_row("Task type", result.task_type.value)
    table.add_row("Target density", f"{result.target_density:.2f}")
    table.add_row("Actual density", f"{result.actual_density:.2f}")
    table.add_row("Original tokens (est.)", str(result.original_tokens))
    table.add_row("Compressed tokens (est.)", str(result.compressed_tokens))
    table.add_row("Savings", f"{result.savings_pct:.0%}")
    table.add_row("Backend", result.backend_name)
    table.add_row("Output", str(out))

    console.print(Panel(table, title="[bold]denser[/bold]", border_style="cyan"))

    if show_rationale and result.rationale:
        console.print(
            Panel(
                result.rationale,
                title="[bold]Rationale[/bold]",
                border_style="yellow",
            )
        )


@main.command("info")
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    default=None,
    help="Show detail for a specific task type. If omitted, shows the summary table.",
)
def info_cmd(task_type: str | None) -> None:
    """Show the taxonomy summary (offline, no API calls)."""
    if task_type is None:
        table = Table(title="denser task types")
        table.add_column("Type", style="cyan")
        table.add_column("Exploratory density range")
        table.add_column("Role")
        for tt, spec in SPECS.items():
            low, high = spec.density_range
            table.add_row(tt.value, f"{low:.2f} - {high:.2f}", spec.role_summary[:60] + "...")
        console.print(table)
        return

    tt = TaskType.parse(task_type)
    spec = SPECS[tt]
    low, high = spec.density_range
    body = (
        f"[bold]Role:[/bold] {spec.role_summary}\n\n"
        f"[bold]Exploratory target range:[/bold] {low:.2f} - {high:.2f} "
        f"(default target: {spec.default_target_density:.2f})\n\n"
        "[bold]Preserve:[/bold]\n" + "\n".join(f"  - {item}" for item in spec.preserve) + "\n\n"
        "[bold]Strip:[/bold]\n" + "\n".join(f"  - {item}" for item in spec.strip)
    )
    console.print(Panel(body, title=f"[cyan]{tt.value}[/cyan]"))


@main.command("eval")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
    help="Instruction profile; built-in tasks are structural checks.",
)
@click.option(
    "--compare-to",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="If given, evaluate the second file as the 'compressed' version and report delta.",
)
@click.option(
    "--n-trials",
    type=int,
    default=1,
    show_default=True,
    help="Runs per test case. Higher = more stable but more API calls.",
)
@click.option(
    "--judge-model",
    default="claude-haiku-4-5-20251001",
    show_default=True,
    help="Model used as the evaluation judge.",
)
def eval_cmd(
    input_file: Path,
    task_type: str,
    compare_to: Path | None,
    n_trials: int,
    judge_model: str,
) -> None:
    """Evaluate INPUT_FILE with built-in structural checks or supplied tasks."""
    text = input_file.read_text(encoding="utf-8")

    try:
        judge = ClaudeBackend(model=judge_model, temperature=0.0)
    except BackendError as e:
        console.print(f"[red]Backend error:[/red] {e}", style="bold")
        sys.exit(2)

    if compare_to is None:
        with console.status(f"Evaluating [cyan]{input_file.name}[/cyan]..."):
            eval_report = evaluate_fn(
                text,
                task_type=task_type,
                judge_backend=judge,
                n_trials=n_trials,
            )
        _print_eval_report(eval_report, input_file.name)
        return

    compressed_text = compare_to.read_text(encoding="utf-8")
    with console.status(
        f"Comparing [cyan]{input_file.name}[/cyan] vs [green]{compare_to.name}[/green]..."
    ):
        comparison_report = compare_fn(
            original=text,
            compressed=compressed_text,
            task_type=task_type,
            judge_backend=judge,
            n_trials=n_trials,
        )
    _print_comparison_report(comparison_report, input_file.name, compare_to.name)


def _print_eval_report(report: EvalReport, label: str) -> None:
    table = Table(title=f"[bold]observed checks[/bold]: {label}", show_lines=False)
    table.add_column("Task")
    table.add_column("Cases")
    table.add_column("Pass rate", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Status", justify="center")
    for tr in report.task_results:
        status = "[green]PASS[/green]" if tr.passed else "[red]FAIL[/red]"
        table.add_row(
            tr.task_name,
            str(len(tr.case_results)),
            f"{tr.overall_pass_rate:.2%}",
            f"{tr.pass_threshold:.2%}",
            status,
        )
    console.print(table)
    console.print(
        f"\n[bold]Overall pass rate:[/bold] {report.overall_pass_rate:.2%} "
        f"across {report.n_tasks} tasks / {report.n_cases} cases; "
        f"operational errors: {report.n_errors}"
    )


def _print_comparison_report(
    report: ComparisonReport,
    original_label: str,
    compressed_label: str,
) -> None:
    table = Table(title="[bold]eval: original vs. compressed[/bold]")
    table.add_column("")
    table.add_column(original_label, justify="right")
    table.add_column(compressed_label, justify="right")
    table.add_column("delta", justify="right")

    def _fmt_delta(d: float) -> str:
        if d > 0:
            return f"[green]+{d:.2%}[/green]"
        if d < 0:
            return f"[red]{d:.2%}[/red]"
        return f"{d:.2%}"

    table.add_row(
        "Overall pass rate",
        f"{report.original.overall_pass_rate:.2%}",
        f"{report.compressed.overall_pass_rate:.2%}",
        _fmt_delta(report.delta),
    )
    for orig_tr, comp_tr in zip(
        report.original.task_results, report.compressed.task_results, strict=True
    ):
        d = comp_tr.overall_pass_rate - orig_tr.overall_pass_rate
        table.add_row(
            f"  {orig_tr.task_name}",
            f"{orig_tr.overall_pass_rate:.2%}",
            f"{comp_tr.overall_pass_rate:.2%}",
            _fmt_delta(d),
        )
    console.print(table)
    console.print(
        f"Operational errors: original={report.original.n_errors}, "
        f"candidate={report.compressed.n_errors}"
    )


@main.command("audit")
@click.argument("baseline_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("variant_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--suite",
    "suite_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="UTF-8 JSON file containing asset-specific replay cases.",
)
@click.option(
    "--negative-control",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Known-bad context variant used to prove that the replay suite is sensitive.",
)
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
)
@click.option(
    "--backend",
    type=click.Choice(REPLAY_BACKEND_CHOICES, case_sensitive=False),
    default="claude",
    show_default=True,
)
@click.option("--base-url", default=None, help="Base URL for openai-compat backend.")
@click.option("--model", default=None, help="Execution model id; defaults depend on backend.")
@click.option(
    "--openai-thinking-mode",
    type=click.Choice(["provider-default", "enabled", "disabled"]),
    default="provider-default",
    show_default=True,
    help="Reasoning mode for compatible providers that accept extra_body.thinking.",
)
@click.option(
    "--codex-cli-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    envvar="DENSER_CODEX_CLI",
    help="Independent Codex CLI executable; never use the desktop WindowsApps binary.",
)
@click.option(
    "--codex-timeout",
    type=click.FloatRange(min=1.0),
    default=180.0,
    show_default=True,
    help="Per-call timeout in seconds for the codex-cli backend.",
)
@click.option(
    "--codex-reasoning-effort",
    type=click.Choice(["none", "low", "medium", "high", "xhigh", "max"]),
    default="medium",
    show_default=True,
)
@click.option(
    "--codex-respect-system-proxy/--no-codex-respect-system-proxy",
    default=False,
    help="Enable Codex CLI's experimental Windows system-proxy support.",
)
@click.option(
    "--codex-capability-profile",
    type=click.Choice(CODEX_CAPABILITY_PROFILES),
    default="standard",
    show_default=True,
    help="Use text-only only when the task needs no files, commands, network, plugins, or skills.",
)
@click.option("--n-trials", type=click.IntRange(min=1), default=1, show_default=True)
@click.option(
    "--seed",
    type=int,
    default=0,
    show_default=True,
    help="Reproducible call-order seed for the paired baseline/variant replay.",
)
@click.option(
    "--progress/--no-progress",
    default=True,
    show_default=True,
    help="Print each completed replay call and the total call count.",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the versioned audit report to a new JSON file.",
)
def audit_cmd(
    baseline_file: Path,
    variant_file: Path,
    suite_file: Path,
    negative_control: Path | None,
    task_type: str,
    backend: str,
    base_url: str | None,
    model: str | None,
    openai_thinking_mode: str,
    codex_cli_path: Path | None,
    codex_timeout: float,
    codex_reasoning_effort: str,
    codex_respect_system_proxy: bool,
    codex_capability_profile: str,
    n_trials: int,
    seed: int,
    progress: bool,
    json_out: Path | None,
) -> None:
    """Audit whether VARIANT_FILE preserves BASELINE_FILE behavior."""
    if json_out is not None:
        _validate_new_output_paths(baseline_file, json_out, None)
        protected_inputs = [variant_file, suite_file, negative_control]
        if any(
            path is not None and json_out.resolve() == path.resolve() for path in protected_inputs
        ):
            raise click.ClickException("Refusing to overwrite an audit input file.")

    try:
        baseline = baseline_file.read_text(encoding="utf-8")
        variant = variant_file.read_text(encoding="utf-8")
        control_text = (
            None if negative_control is None else negative_control.read_text(encoding="utf-8")
        )
        suite = load_replay_suite(suite_file)
        backend_obj = _build_backend(
            backend,
            model=model,
            base_url=base_url,
            openai_thinking_mode=openai_thinking_mode,
            codex_cli_path=codex_cli_path,
            codex_timeout=codex_timeout,
            codex_reasoning_effort=codex_reasoning_effort,
            codex_respect_system_proxy=codex_respect_system_proxy,
            codex_capability_profile=codex_capability_profile,
        )
        progress_callback = _print_replay_progress if progress else None
        report = audit_context_fn(
            baseline=baseline,
            variant=variant,
            negative_control=control_text,
            task_type=task_type,
            tasks=suite,
            backend=backend_obj,
            n_trials=n_trials,
            seed=seed,
            on_progress=progress_callback,
        )
    except (BackendError, UnicodeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    _print_context_audit(report, baseline_file.name, variant_file.name)
    if json_out is not None:
        json_out.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"Wrote audit JSON -> {json_out}")

    exit_code = {
        AuditDecision.PRESERVED: 0,
        AuditDecision.REGRESSED: 2,
        AuditDecision.REVIEW: 3,
        AuditDecision.INCONCLUSIVE: 3,
    }[report.decision]
    if exit_code:
        raise click.exceptions.Exit(exit_code)


def _print_context_audit(
    report: ContextAuditReport,
    baseline_label: str,
    variant_label: str,
) -> None:
    table = Table(title="[bold]context behavior audit[/bold]")
    table.add_column("Task")
    table.add_column(baseline_label, justify="right")
    table.add_column(variant_label, justify="right")
    table.add_column("Delta", justify="right")
    for baseline, variant in zip(
        report.comparison.original.task_results,
        report.comparison.candidate.task_results,
        strict=True,
    ):
        delta = variant.overall_pass_rate - baseline.overall_pass_rate
        table.add_row(
            baseline.task_name,
            f"{baseline.overall_pass_rate:.2%}",
            f"{variant.overall_pass_rate:.2%}",
            f"{delta:+.2%}",
        )
    console.print(table)

    control_status = {
        None: "not run",
        True: "detected",
        False: "not detected",
    }[report.negative_control_detected]
    observed = report.observed_input_reduction_pct
    observed_summary = (
        "unavailable"
        if observed is None
        else (
            f"{report.baseline_input_tokens} -> {report.variant_input_tokens} "
            f"({observed:+.2%} reduction)"
        )
    )
    decision_style = {
        AuditDecision.PRESERVED: "green",
        AuditDecision.REGRESSED: "red",
        AuditDecision.REVIEW: "yellow",
        AuditDecision.INCONCLUSIVE: "yellow",
    }[report.decision]
    summary = (
        f"Decision: [{decision_style}]{report.decision.value}[/{decision_style}]\n"
        f"Reason: {escape(report.decision_reason)}\n"
        f"Asset estimate: {report.baseline_estimated_tokens} -> "
        f"{report.variant_estimated_tokens} "
        f"({report.estimated_token_reduction_pct:+.2%} reduction)\n"
        f"Provider-reported full input: {observed_summary}\n"
        f"Negative control: {control_status}"
    )
    console.print(Panel.fit(summary, title="Audit verdict"))


@main.command("replay")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--suite",
    "suite_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="UTF-8 JSON file containing asset-specific replay cases.",
)
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
)
@click.option(
    "--compare-to",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Candidate instruction file to compare with the original.",
)
@click.option(
    "--backend",
    type=click.Choice(REPLAY_BACKEND_CHOICES, case_sensitive=False),
    default="claude",
    show_default=True,
)
@click.option("--base-url", default=None, help="Base URL for openai-compat backend.")
@click.option("--model", default=None, help="Execution model id; defaults depend on backend.")
@click.option(
    "--openai-thinking-mode",
    type=click.Choice(["provider-default", "enabled", "disabled"]),
    default="provider-default",
    show_default=True,
    help="Reasoning mode for compatible providers that accept extra_body.thinking.",
)
@click.option(
    "--codex-cli-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    envvar="DENSER_CODEX_CLI",
    help="Independent Codex CLI executable; never use the desktop WindowsApps binary.",
)
@click.option(
    "--codex-timeout",
    type=click.FloatRange(min=1.0),
    default=180.0,
    show_default=True,
    help="Per-call timeout in seconds for the codex-cli backend.",
)
@click.option(
    "--codex-reasoning-effort",
    type=click.Choice(["none", "low", "medium", "high", "xhigh", "max"]),
    default="medium",
    show_default=True,
)
@click.option(
    "--codex-respect-system-proxy/--no-codex-respect-system-proxy",
    default=False,
    help="Enable Codex CLI's experimental Windows system-proxy support.",
)
@click.option(
    "--codex-capability-profile",
    type=click.Choice(CODEX_CAPABILITY_PROFILES),
    default="standard",
    show_default=True,
    help="Use text-only only when the task needs no files, commands, network, plugins, or skills.",
)
@click.option("--n-trials", type=click.IntRange(min=1), default=1, show_default=True)
@click.option(
    "--seed",
    type=int,
    default=0,
    show_default=True,
    help="Reproducible call-order seed for paired comparisons.",
)
@click.option(
    "--progress/--no-progress",
    default=True,
    show_default=True,
    help="Print each completed replay call and the total call count.",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the replay report to a new JSON file.",
)
def replay_cmd(
    input_file: Path,
    suite_file: Path,
    task_type: str,
    compare_to: Path | None,
    backend: str,
    base_url: str | None,
    model: str | None,
    openai_thinking_mode: str,
    codex_cli_path: Path | None,
    codex_timeout: float,
    codex_reasoning_effort: str,
    codex_respect_system_proxy: bool,
    codex_capability_profile: str,
    n_trials: int,
    seed: int,
    progress: bool,
    json_out: Path | None,
) -> None:
    """Execute asset-specific behavior cases against INPUT_FILE."""
    if json_out is not None:
        _validate_new_output_paths(input_file, json_out, None)
        protected_inputs = [suite_file, compare_to]
        if any(
            path is not None and json_out.resolve() == path.resolve() for path in protected_inputs
        ):
            raise click.ClickException("Refusing to overwrite a replay input file.")

    try:
        tasks = load_replay_suite(suite_file)
        backend_obj = _build_backend(
            backend,
            model=model,
            base_url=base_url,
            temperature=0.0,
            codex_cli_path=codex_cli_path,
            codex_timeout=codex_timeout,
            codex_reasoning_effort=codex_reasoning_effort,
            codex_respect_system_proxy=codex_respect_system_proxy,
            openai_thinking_mode=openai_thinking_mode,
            codex_capability_profile=codex_capability_profile,
        )
        original = input_file.read_text(encoding="utf-8")
        progress_callback = _print_replay_progress if progress else None
        if compare_to is None:
            replay_report = replay_fn(
                original,
                task_type=task_type,
                tasks=tasks,
                backend=backend_obj,
                n_trials=n_trials,
                on_progress=progress_callback,
            )
            _print_replay_report(replay_report, input_file.name)
            report_data = replay_report.to_dict()
            replay_passed = replay_report.n_errors == 0 and all(
                result.passed for result in replay_report.task_results
            )
        else:
            candidate = compare_to.read_text(encoding="utf-8")
            comparison_report = compare_replay_fn(
                original=original,
                candidate=candidate,
                task_type=task_type,
                tasks=tasks,
                backend=backend_obj,
                n_trials=n_trials,
                seed=seed,
                on_progress=progress_callback,
            )
            _print_replay_comparison(comparison_report, input_file.name, compare_to.name)
            report_data = comparison_report.to_dict()
            replay_passed = all(
                original_result.n_errors + candidate_result.n_errors == 0
                and candidate_result.passed
                and candidate_result.overall_pass_rate >= original_result.overall_pass_rate
                for original_result, candidate_result in zip(
                    comparison_report.original.task_results,
                    comparison_report.candidate.task_results,
                    strict=True,
                )
            )
    except (BackendError, UnicodeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if json_out is not None:
        json_out.write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"Wrote replay JSON -> {json_out}")
    if not replay_passed:
        raise click.exceptions.Exit(2)


def _print_replay_progress(progress: ReplayProgress) -> None:
    console.print(
        f"Replay progress {progress.completed_calls}/{progress.total_calls}: "
        f"{escape(progress.side)} | {escape(progress.task_name)}/{escape(progress.case_name)} "
        f"| trial {progress.trial_index}/{progress.n_trials}"
    )


def _print_replay_report(report: ReplayReport, label: str) -> None:
    table = Table(title=f"[bold]behavior replay[/bold]: {label}")
    table.add_column("Task")
    table.add_column("Cases", justify="right")
    table.add_column("Pass rate", justify="right")
    table.add_column("Errors", justify="right")
    for result in report.task_results:
        table.add_row(
            result.task_name,
            str(len(result.case_results)),
            f"{result.overall_pass_rate:.2%}",
            str(result.n_errors),
        )
    console.print(table)
    console.print(
        f"Backend: {escape(report.backend_name)}; overall: {report.overall_pass_rate:.2%}; "
        f"operational errors: {report.n_errors}"
    )
    usage = report.usage_totals
    if any(usage.values()):
        console.print(
            "Usage: "
            f"input={usage['input_tokens']}, cached={usage['cached_input_tokens']}, "
            f"output={usage['output_tokens']}, reasoning={usage['reasoning_output_tokens']}"
        )


def _print_replay_comparison(
    report: ReplayComparisonReport,
    original_label: str,
    candidate_label: str,
) -> None:
    table = Table(title="[bold]behavior replay: original vs. candidate[/bold]")
    table.add_column("Task")
    table.add_column(original_label, justify="right")
    table.add_column(candidate_label, justify="right")
    table.add_column("Delta", justify="right")
    for original, candidate in zip(
        report.original.task_results,
        report.candidate.task_results,
        strict=True,
    ):
        delta = candidate.overall_pass_rate - original.overall_pass_rate
        table.add_row(
            original.task_name,
            f"{original.overall_pass_rate:.2%}",
            f"{candidate.overall_pass_rate:.2%}",
            f"{delta:+.2%}",
        )
    console.print(table)
    console.print(
        f"Backend: {escape(report.original.backend_name)}; seed: {report.seed}; "
        f"operational errors: original={report.original.n_errors}, "
        f"candidate={report.candidate.n_errors}"
    )
    original_usage = report.original.usage_totals
    candidate_usage = report.candidate.usage_totals
    if any(original_usage.values()) or any(candidate_usage.values()):
        console.print(
            "Usage input/output: "
            f"original={original_usage['input_tokens']}/{original_usage['output_tokens']}; "
            f"candidate={candidate_usage['input_tokens']}/{candidate_usage['output_tokens']}"
        )


@main.command("curve")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
)
@click.option(
    "--densities",
    default="0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0",
    show_default=True,
    help="Comma-separated target densities to sample.",
)
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="If given, save the curve as a PNG (requires `denser[plot]`).",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="If given, also dump the curve points as JSON.",
)
@click.option("--n-trials", type=int, default=1, show_default=True)
@click.option("--model", default="claude-opus-4-6", show_default=True)
@click.option("--judge-model", default="claude-haiku-4-5-20251001", show_default=True)
def curve_cmd(
    input_file: Path,
    task_type: str,
    densities: str,
    out: Path | None,
    json_out: Path | None,
    n_trials: int,
    model: str,
    judge_model: str,
) -> None:
    """Run and optionally plot an experimental density sweep for INPUT_FILE."""
    text = input_file.read_text(encoding="utf-8")
    try:
        rhos = tuple(float(x.strip()) for x in densities.split(",") if x.strip())
    except ValueError:
        console.print(f"[red]Invalid --densities: {densities!r}[/red]")
        sys.exit(2)

    try:
        compressor = ClaudeBackend(model=model)
        judge = ClaudeBackend(model=judge_model, temperature=0.0)
    except BackendError as e:
        console.print(f"[red]Backend error:[/red] {e}", style="bold")
        sys.exit(2)

    with console.status(f"Sweeping {len(rhos)} densities for [cyan]{input_file.name}[/cyan]..."):
        c = curve_fn(
            text,
            task_type=task_type,
            densities=rhos,
            compressor_backend=compressor,
            judge_backend=judge,
            n_trials=n_trials,
        )

    table = Table(title=f"[bold]Experimental density sweep: {task_type}[/bold]")
    table.add_column("target density", justify="right")
    table.add_column("actual density", justify="right")
    table.add_column("pass rate", justify="right")
    for p in c.points:
        table.add_row(
            f"{p.target_density:.2f}",
            f"{p.actual_density:.2f}",
            f"{p.pass_rate:.2%}",
        )
    console.print(table)
    console.print(
        f"\n[bold]Best observed/fitted density:[/bold] {c.peak_density:.2f} "
        f"(observed/fitted pass rate {c.peak_pass_rate:.2%})"
    )

    if json_out:
        import json

        json_out.write_text(json.dumps(c.to_dict(), indent=2), encoding="utf-8")
        console.print(f"Wrote curve JSON -> {json_out}")

    if out:
        try:
            c.plot(out)
            console.print(f"Wrote plot -> {out}")
        except ImportError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(2)


if __name__ == "__main__":  # pragma: no cover
    main()
