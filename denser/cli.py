"""Command-line interface.

Entry point registered via pyproject.toml as `denser`.

Commands:
- `denser compress` — compress a single file
- `denser info` — show the taxonomy summary (offline, no API calls)

`denser curve` and `denser eval` are v0.2 — surfaced as not-yet-implemented.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from denser import __version__
from denser.backends import BackendError, ClaudeBackend
from denser.compress import compress
from denser.curve import curve as curve_fn
from denser.eval import compare as compare_fn
from denser.eval import evaluate as evaluate_fn
from denser.taxonomy import SPECS, TaskType

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="denser")
def main() -> None:
    """denser — find the signal density sweet spot for LLM inputs."""


@main.command("compress")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "task_type",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    required=True,
    help="The task type to compress for (drives strategy and sweet-spot density).",
)
@click.option(
    "--density",
    type=float,
    default=None,
    help="Target density (compressed/original tokens). Default: taxonomy midpoint.",
)
@click.option(
    "--model",
    default="claude-opus-4-6",
    help="Claude model to use as the compressor.",
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
    model: str,
    out: Path | None,
    show_rationale: bool,
) -> None:
    """Compress the contents of INPUT_FILE for a given task type."""
    text = input_file.read_text(encoding="utf-8")

    try:
        backend = ClaudeBackend(model=model)
    except BackendError as e:
        console.print(f"[red]Backend error:[/red] {e}", style="bold")
        sys.exit(2)

    console.print(f"Compressing [bold]{input_file.name}[/bold] as [cyan]{task_type}[/cyan]...")
    try:
        result = compress(text, task_type=task_type, target_density=density, backend=backend)
    except (ValueError, BackendError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if out is None:
        out = input_file.with_suffix(f".dense{input_file.suffix}")
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
        table.add_column("Density peak ρ*")
        table.add_column("Role")
        for tt, spec in SPECS.items():
            low, high = spec.density_range
            table.add_row(tt.value, f"{low:.2f} – {high:.2f}", spec.role_summary[:60] + "...")
        console.print(table)
        return

    tt = TaskType.parse(task_type)
    spec = SPECS[tt]
    low, high = spec.density_range
    body = (
        f"[bold]Role:[/bold] {spec.role_summary}\n\n"
        f"[bold]Density sweet spot:[/bold] {low:.2f} – {high:.2f} "
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
    help="The task type — drives which golden tasks load.",
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
    """Evaluate INPUT_FILE against golden tasks for its task type."""
    text = input_file.read_text(encoding="utf-8")

    try:
        judge = ClaudeBackend(model=judge_model, temperature=0.0)
    except BackendError as e:
        console.print(f"[red]Backend error:[/red] {e}", style="bold")
        sys.exit(2)

    if compare_to is None:
        with console.status(f"Evaluating [cyan]{input_file.name}[/cyan]..."):
            report = evaluate_fn(
                text,
                task_type=task_type,
                judge_backend=judge,
                n_trials=n_trials,
            )
        _print_eval_report(report, input_file.name)
        return

    compressed_text = compare_to.read_text(encoding="utf-8")
    with console.status(
        f"Comparing [cyan]{input_file.name}[/cyan] vs [green]{compare_to.name}[/green]..."
    ):
        report = compare_fn(
            original=text,
            compressed=compressed_text,
            task_type=task_type,
            judge_backend=judge,
            n_trials=n_trials,
        )
    _print_comparison_report(report, input_file.name, compare_to.name)


def _print_eval_report(report, label: str) -> None:
    table = Table(title=f"[bold]eval[/bold] — {label}", show_lines=False)
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
        f"across {report.n_tasks} tasks / {report.n_cases} cases"
    )


def _print_comparison_report(report, original_label: str, compressed_label: str) -> None:
    table = Table(title="[bold]eval: original vs. compressed[/bold]")
    table.add_column("")
    table.add_column(original_label, justify="right")
    table.add_column(compressed_label, justify="right")
    table.add_column("Δ", justify="right")

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
    """Compute and (optionally) plot the Signal Density Curve for INPUT_FILE."""
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

    table = Table(title=f"[bold]Signal Density Curve — {task_type}[/bold]")
    table.add_column("target ρ", justify="right")
    table.add_column("actual ρ", justify="right")
    table.add_column("pass rate", justify="right")
    for p in c.points:
        table.add_row(
            f"{p.target_density:.2f}",
            f"{p.actual_density:.2f}",
            f"{p.pass_rate:.2%}",
        )
    console.print(table)
    console.print(
        f"\n[bold]Peak:[/bold] ρ* = {c.peak_density:.2f} (pass rate {c.peak_pass_rate:.2%})"
    )

    if json_out:
        import json

        json_out.write_text(json.dumps(c.to_dict(), indent=2), encoding="utf-8")
        console.print(f"Wrote curve JSON → {json_out}")

    if out:
        try:
            c.plot(out)
            console.print(f"Wrote plot → {out}")
        except ImportError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(2)


if __name__ == "__main__":  # pragma: no cover
    main()
