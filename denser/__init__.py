"""Behavior-fidelity audits for version-controlled LLM context."""

# Load a `.env` file from the current working directory if python-dotenv is
# installed. This is the recommended way to pass API keys to denser without
# persisting them in shell history or Windows registry. Silent if dotenv is
# missing — users who set env vars directly are unaffected.
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv()
except ImportError:  # pragma: no cover
    pass

from denser.audit import (
    AUDIT_REPORT_SCHEMA_VERSION,
    AuditDecision,
    ContextAuditReport,
    audit_context,
)
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
from denser.inspection import (
    ContractCategory,
    ContractItem,
    InspectionAction,
    InspectionReport,
    PreservationContract,
    RiskLevel,
    SourceSpan,
    inspect,
)
from denser.optimization import (
    EVIDENCE_SCHEMA_VERSION,
    CandidateKind,
    OptimizationCandidate,
    OptimizationReport,
    optimize,
)
from denser.replay import (
    LEGACY_REPLAY_SUITE_SCHEMA_VERSION,
    REPLAY_REPORT_SCHEMA_VERSION,
    REPLAY_SUITE_SCHEMA_VERSION,
    MatchMode,
    ReplayCase,
    ReplayCaseResult,
    ReplayCategory,
    ReplayComparisonReport,
    ReplayProgress,
    ReplayReport,
    ReplaySuite,
    ReplaySuiteAuthoring,
    ReplaySuiteFreeze,
    ReplaySuiteRole,
    ReplayTask,
    ReplayTaskResult,
    compare_replay,
    load_replay_suite,
    load_replay_tasks,
    replay,
)
from denser.taxonomy import SPECS, TaskSpec, TaskType
from denser.tokens import (
    AnthropicTokenCounter,
    HeuristicTokenCounter,
    TokenCounter,
    TokenCountError,
)
from denser.verification import (
    BehaviorTaskResult,
    ContractItemResult,
    VerificationDecision,
    VerificationReport,
    VerificationStatus,
    verify,
)

__version__ = "0.2.0a1"

__all__ = [
    "AUDIT_REPORT_SCHEMA_VERSION",
    "AnthropicTokenCounter",
    "AuditDecision",
    "BehaviorTaskResult",
    "CandidateKind",
    "CaseResult",
    "ComparisonReport",
    "CompressionResult",
    "ContractCategory",
    "ContractItem",
    "ContractItemResult",
    "ContextAuditReport",
    "DensityCurve",
    "DensityPoint",
    "EVIDENCE_SCHEMA_VERSION",
    "EvalReport",
    "GoldenTask",
    "HeuristicTokenCounter",
    "InspectionAction",
    "InspectionReport",
    "LEGACY_REPLAY_SUITE_SCHEMA_VERSION",
    "MatchMode",
    "REPLAY_REPORT_SCHEMA_VERSION",
    "REPLAY_SUITE_SCHEMA_VERSION",
    "OptimizationCandidate",
    "OptimizationReport",
    "PreservationContract",
    "RiskLevel",
    "ReplayCase",
    "ReplayCaseResult",
    "ReplayCategory",
    "ReplayComparisonReport",
    "ReplayProgress",
    "ReplayReport",
    "ReplaySuite",
    "ReplaySuiteAuthoring",
    "ReplaySuiteFreeze",
    "ReplaySuiteRole",
    "ReplayTask",
    "ReplayTaskResult",
    "SPECS",
    "SourceSpan",
    "TaskResult",
    "TaskSpec",
    "TaskType",
    "TestCase",
    "TokenCounter",
    "TokenCountError",
    "VerificationDecision",
    "VerificationReport",
    "VerificationStatus",
    "compare",
    "compare_replay",
    "audit_context",
    "compress",
    "curve",
    "evaluate",
    "inspect",
    "load_golden_tasks",
    "load_replay_suite",
    "load_replay_tasks",
    "optimize",
    "replay",
    "verify",
]
