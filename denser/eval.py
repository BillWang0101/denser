"""Evaluation harness.

The core of denser's eval-first methodology: run a text through a set of
**golden tasks** for its task type, measure how often an LLM judge says the
text does its job, report a pass-rate.

Two entry points:

- `evaluate(text, task_type, ...)` — score a single text
- `compare(original, compressed, task_type, ...)` — side-by-side before/after

Golden tasks live in `denser/fixtures/golden/<task_type>/*.json`. Users and
contributors can also pass custom tasks directly.
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from denser.backends import Backend, ClaudeBackend
from denser.taxonomy import TaskType

logger = logging.getLogger(__name__)

# Default judge model: Haiku is 10-20× cheaper than Opus and sufficient for
# simple yes/no or exact-match judgments. Configurable via `judge_backend`.
DEFAULT_JUDGE_MODEL = "claude-haiku-4-5-20251001"

# Placeholder used in `task_prompt` where the input text should be substituted.
INPUT_PLACEHOLDER = "{input}"


@dataclass(frozen=True)
class TestCase:
    """A single input/expected pair within a golden task.

    `vars` gets substituted into the `task_prompt` template alongside `{input}`.
    `expected` can be a string or list of acceptable strings (any match = pass).
    """

    name: str
    vars: dict[str, str]
    expected: str | list[str]

    def matches(self, judge_output: str) -> bool:
        """Return True if the judge's normalized output matches an expected value."""
        normalized = _normalize_judge_output(judge_output)
        expected_list = [self.expected] if isinstance(self.expected, str) else list(self.expected)
        for exp in expected_list:
            if _normalize_judge_output(exp) == normalized:
                return True
        return False


@dataclass(frozen=True)
class GoldenTask:
    """A golden task: a prompt template that tests whether a text does its job.

    The `task_prompt` is a template containing `{input}` (substituted with the
    text being evaluated) plus any `vars` placeholders from individual test
    cases. The judge runs the filled prompt and its output is matched against
    each test case's `expected`.
    """

    task_type: TaskType
    name: str
    description: str
    task_prompt: str
    test_cases: tuple[TestCase, ...]
    pass_threshold: float = 0.9

    @classmethod
    def from_dict(cls, data: dict) -> GoldenTask:
        """Construct a GoldenTask from a parsed JSON dict."""
        tt = TaskType.parse(data["task_type"])
        cases = tuple(
            TestCase(
                name=c["name"],
                vars=dict(c.get("vars", {})),
                expected=c["expected"],
            )
            for c in data["test_cases"]
        )
        return cls(
            task_type=tt,
            name=data["name"],
            description=data.get("description", ""),
            task_prompt=data["task_prompt"],
            test_cases=cases,
            pass_threshold=float(data.get("pass_threshold", 0.9)),
        )

    def fill(self, text: str, case: TestCase) -> str:
        """Instantiate the task prompt with the input text and a test case's vars."""
        if INPUT_PLACEHOLDER not in self.task_prompt:
            raise ValueError(
                f"GoldenTask {self.name!r}: task_prompt must contain {INPUT_PLACEHOLDER!r}"
            )
        prompt = self.task_prompt.replace(INPUT_PLACEHOLDER, text)
        for key, val in case.vars.items():
            prompt = prompt.replace(f"{{{key}}}", val)
        return prompt


@dataclass
class CaseResult:
    """Outcome of evaluating a single test case across N trials."""

    case_name: str
    n_trials: int
    n_passed: int
    judge_outputs: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.n_trials == 0:
            return 0.0
        return self.n_passed / self.n_trials


@dataclass
class TaskResult:
    """Outcome of evaluating a single golden task across its test cases."""

    task_name: str
    case_results: list[CaseResult]
    pass_threshold: float

    @property
    def overall_pass_rate(self) -> float:
        if not self.case_results:
            return 0.0
        return statistics.fmean(cr.pass_rate for cr in self.case_results)

    @property
    def passed(self) -> bool:
        return self.overall_pass_rate >= self.pass_threshold


@dataclass
class EvalReport:
    """Aggregate report across all golden tasks for a single text."""

    task_type: TaskType
    task_results: list[TaskResult]

    @property
    def overall_pass_rate(self) -> float:
        if not self.task_results:
            return 0.0
        return statistics.fmean(tr.overall_pass_rate for tr in self.task_results)

    @property
    def n_tasks(self) -> int:
        return len(self.task_results)

    @property
    def n_cases(self) -> int:
        return sum(len(tr.case_results) for tr in self.task_results)


@dataclass
class ComparisonReport:
    """Side-by-side evaluation of original vs. compressed text."""

    task_type: TaskType
    original: EvalReport
    compressed: EvalReport

    @property
    def delta(self) -> float:
        """Compressed pass rate minus original pass rate. Positive = improvement."""
        return self.compressed.overall_pass_rate - self.original.overall_pass_rate


# ---- judge output normalization ----

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"[\s_]+")


def _normalize_judge_output(raw: str) -> str:
    """Normalize a judge's free-form response into a canonical form.

    Rules:
      1. Strip whitespace, lowercase
      2. Strip surrounding punctuation
      3. Collapse internal whitespace to single spaces
      4. If the text starts with 'yes'/'no' followed by a word boundary,
         collapse to just that word (judges often append reasoning)
    """
    if raw is None:
        return ""
    s = raw.strip().lower()
    # Yes/no shortcut: if the first token is yes/no, keep only that.
    m = re.match(r"^(yes|no)\b", s)
    if m:
        return m.group(1)
    # Otherwise: strip punctuation, collapse whitespace.
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


# ---- fixtures loader ----


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "golden"


def load_golden_tasks(task_type: TaskType | str) -> list[GoldenTask]:
    """Load all built-in golden tasks for a task type from `denser/fixtures/golden/`.

    Each JSON file under `denser/fixtures/golden/<task_type>/` becomes one
    GoldenTask. Returns an empty list if no fixtures exist for that type.
    """
    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    dir_ = _fixtures_dir() / tt.value
    if not dir_.is_dir():
        return []
    tasks: list[GoldenTask] = []
    for path in sorted(dir_.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tasks.append(GoldenTask.from_dict(data))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to load golden task %s: %s", path, e)
    return tasks


# ---- eval engine ----


def evaluate(
    text: str,
    *,
    task_type: TaskType | str,
    golden_tasks: list[GoldenTask] | None = None,
    judge_backend: Backend | None = None,
    n_trials: int = 1,
) -> EvalReport:
    """Evaluate `text` for a given task type against a set of golden tasks.

    Parameters
    ----------
    text : str
        The text being evaluated (e.g., a skill body or system prompt).
    task_type : TaskType | str
        Which task type to evaluate as.
    golden_tasks : list[GoldenTask] | None
        Tasks to run. If None, loads built-in fixtures for the task type.
    judge_backend : Backend | None
        LLM backend used as the judge. If None, uses `ClaudeBackend` with
        Haiku 4.5 (cheap, sufficient for structured judgments).
    n_trials : int
        How many times to run each test case (to average out judge noise).
        Default 1 for speed; production benchmarks use 30.

    Returns
    -------
    EvalReport
    """
    if not text or not text.strip():
        raise ValueError("Cannot evaluate empty text")
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")

    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    tasks = golden_tasks if golden_tasks is not None else load_golden_tasks(tt)
    if not tasks:
        return EvalReport(task_type=tt, task_results=[])

    if judge_backend is None:
        judge_backend = ClaudeBackend(model=DEFAULT_JUDGE_MODEL, temperature=0.0)

    # The judge gets a minimal system prompt — instructions are in the task prompt.
    judge_system = (
        "You are a careful evaluator. Follow the instructions in the user "
        "message exactly. Respond with only the answer requested — no "
        "explanation, no preamble, no punctuation unless part of the answer."
    )

    task_results: list[TaskResult] = []
    for gt in tasks:
        case_results: list[CaseResult] = []
        for case in gt.test_cases:
            user_prompt = gt.fill(text, case)
            outputs: list[str] = []
            passes = 0
            for _ in range(n_trials):
                try:
                    out = judge_backend.complete(
                        system=judge_system, user=user_prompt, max_tokens=128
                    )
                except Exception as e:
                    logger.warning(
                        "Judge failed on %s/%s: %s", gt.name, case.name, e
                    )
                    out = ""
                outputs.append(out)
                if case.matches(out):
                    passes += 1
            case_results.append(
                CaseResult(
                    case_name=case.name,
                    n_trials=n_trials,
                    n_passed=passes,
                    judge_outputs=outputs,
                )
            )
        task_results.append(
            TaskResult(
                task_name=gt.name,
                case_results=case_results,
                pass_threshold=gt.pass_threshold,
            )
        )

    return EvalReport(task_type=tt, task_results=task_results)


def compare(
    *,
    original: str,
    compressed: str,
    task_type: TaskType | str,
    golden_tasks: list[GoldenTask] | None = None,
    judge_backend: Backend | None = None,
    n_trials: int = 1,
) -> ComparisonReport:
    """Evaluate both original and compressed text against the same golden tasks.

    Returns a `ComparisonReport` with a `delta` property — the change in
    pass-rate. Positive means compression improved task performance; negative
    means it hurt.
    """
    tt = task_type if isinstance(task_type, TaskType) else TaskType.parse(task_type)
    tasks = golden_tasks if golden_tasks is not None else load_golden_tasks(tt)

    orig_report = evaluate(
        original,
        task_type=tt,
        golden_tasks=tasks,
        judge_backend=judge_backend,
        n_trials=n_trials,
    )
    comp_report = evaluate(
        compressed,
        task_type=tt,
        golden_tasks=tasks,
        judge_backend=judge_backend,
        n_trials=n_trials,
    )
    return ComparisonReport(task_type=tt, original=orig_report, compressed=comp_report)


__all__ = [
    "CaseResult",
    "ComparisonReport",
    "EvalReport",
    "GoldenTask",
    "TaskResult",
    "TestCase",
    "compare",
    "evaluate",
    "load_golden_tasks",
]
