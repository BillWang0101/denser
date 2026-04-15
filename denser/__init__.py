"""denser: Find the signal density sweet spot for your LLM prompts, skills, and agent configs."""

from denser.compress import CompressionResult, compress
from denser.curve import DensityCurve, DensityPoint, curve
from denser.eval import (
    CaseResult,
    ComparisonReport,
    EvalReport,
    GoldenTask,
    TaskResult,
    TestCase,
    compare,
    evaluate,
    load_golden_tasks,
)
from denser.taxonomy import SPECS, TaskSpec, TaskType

__version__ = "0.1.0.dev0"

__all__ = [
    "CaseResult",
    "ComparisonReport",
    "CompressionResult",
    "DensityCurve",
    "DensityPoint",
    "EvalReport",
    "GoldenTask",
    "SPECS",
    "TaskResult",
    "TaskSpec",
    "TaskType",
    "TestCase",
    "compare",
    "compress",
    "curve",
    "evaluate",
    "load_golden_tasks",
]
