# denser design direction

Status: active design for the next development cycle. This document supersedes
the product claims in the original four-week launch plan.

## Product promise

denser refactors versioned LLM instruction assets into the shortest candidate
that still passes their behavior tests, with a reviewable diff and evidence for
every removed rule.

Shorter text is not automatically better. The original is always a valid
candidate, and `do not change` is a valid result when evidence is insufficient.

## Scope

The first stable release focuses on static, version-controlled instruction
assets:

- system and developer instructions;
- skills and triggerable procedures;
- tool descriptions and tool-selection rules;
- project instructions such as `AGENTS.md` and `CLAUDE.md`;
- persistent memory rules;
- one-shot implementation or research briefs.

Runtime conversation compaction, RAG document pruning, hidden-vector
compression, and model KV-cache optimization are separate problem spaces and
are out of scope for the first stable release.

## Core workflow

The public workflow should remain small:

1. `inspect` decides whether an asset is safe and worthwhile to refactor, and
   builds a preservation contract.
2. `optimize` produces candidates, verifies them, and returns the shortest
   passing candidate plus an evidence report.
3. `verify` reruns the contract and behavior suite after the asset, model, or
   workload changes.

Existing `compress`, `eval`, and `curve` entry points remain experimental while
this workflow is implemented.

Current implementation status: `inspect`, `verify`, and multi-candidate
`optimize` are available. `verify` can consume caller-supplied behavior tasks
that explicitly name the contract items they cover. `optimize` reuses one
original behavior baseline across candidates and emits a versioned evidence
report. Malformed generator responses and evaluator service errors fail closed.
Evidence reports label the offline heuristic and can instead use a strict
Anthropic provider-counting adapter; provider failures do not silently fall
back to estimates. A deterministic replay runner now executes original and
candidate instructions against the same asset-specific workload, randomizes
paired call order with a recorded seed, and separates service errors from
content failures. The first synthetic redistributable `AGENTS.md` pilot covers
positive, near-miss, failure, permission, and adversarial cases. A second case
uses OpenAI's Apache-2.0 `openai-python` guidance and freezes its candidate in
Git before an independent process authors the holdout. This is chronological
blindness for that candidate, not permanent secrecy after publication. Broader
external workloads and additional provider adapters remain future work.
Its first run also demonstrates why raw results need audit: one incorrect exact
matcher was excluded transparently, a neutral project-policy mutant was caught,
and a disclosed permission inversion exposed a remaining model-prior blind spot.

The replay command can use an independently installed, ChatGPT-authenticated
Codex CLI. Each call is ephemeral and read-only, and the instruction asset is
passed as developer instructions. Replay report schema `v2` added sanitized
per-call execution metadata and provider-reported token totals. Schema `v3`
adds a top-level, allowlisted runtime-configuration snapshot for reproduction.
Replay suite schema `v2` records a holdout's normalized source/candidate hashes,
freeze commit, and non-sensitive authoring identity. Report schema `v4` carries
that evidence and rejects a changed frozen asset before backend execution.
Authentication, executable paths, account details, thread identifiers, and raw
CLI diagnostics are intentionally excluded. Backends that do not expose a
runtime configuration remain compatible and serialize an empty object.

## Preservation contract

Before rewriting, denser identifies obligations with source locations:

- positive and negative triggers;
- required and forbidden behavior;
- permission and escalation rules;
- tool-selection and parameter constraints;
- output schemas and formatting requirements;
- protected literals such as names, numbers, paths, code, and citations;
- failure and recovery behavior;
- the tests that cover each obligation.

An uncovered high-risk obligation is not eligible for automatic removal.

## Verification model

Verification has three layers:

1. **Structural checks** validate protected literals, schemas, references, and
   other deterministic invariants. The current built-in fixtures belong here.
2. **Behavior replay** runs the original and each candidate against the same
   realistic workload and target execution model.
3. **Holdout and adversarial checks** cover near-miss triggers, conflicting
   rules, exceptional paths, and prompt injection that candidate generation did
   not see.

Deterministic assertions take priority over model judges. Model errors are
reported separately from content failures. Candidate selection and final
reporting use different cases to reduce overfitting.

## Candidate selection

denser does not assume that quality is a concave function of compression ratio.
It records observed candidates and selects only among candidates that pass all
hard gates. The default recommendation is the shortest passing candidate, with
a Pareto set when length, behavior, latency, cost, readability, or diff size
trade off.

The Signal Density Curve remains an experimental visualization of observed
points. A quadratic fit is descriptive only and is never proof of a universal
sweet spot.

## Evidence report

Every optimization should eventually return:

- the original, recommended candidate, and alternatives;
- a preservation contract;
- a diff;
- a ledger marking each source unit as kept, merged, rewritten, externalized,
  or rejected for removal;
- the tests covering each change;
- model, tokenizer/counting method, settings, cost, latency, and timestamp;
- operational errors and uncovered risks;
- enough provenance to reproduce or roll back the result.

## Evidence policy

Public performance claims require committed, redistributable inputs, workload
definitions, model and judge identifiers, trial settings, raw results, and a
reproduction command. Small demos and single-model observations must be labeled
as such. Negative results, non-concave observations, and cases where the
original wins are part of the record.

Token estimates are suitable for local previews only. Provider-rendered token
counts are required for cost or performance claims involving a specific model.
Prompt-cache savings and active-context length are reported separately.

## Delivery phases

### Phase 0: credibility reset

- align public claims with committed evidence;
- label built-in fixtures as structural checks;
- make the pre-commit integration advisory;
- fix repository metadata and stale links;
- mark density ranges and curve fitting as exploratory.

### Phase 1: trustworthy core

- implement the preservation contract and source mapping;
- introduce `inspect`, `optimize`, and `verify` as the deep public interface;
- generate multiple candidates and reject malformed model output;
- produce a versioned evidence report;
- add provider-aware token counting behind internal adapters.

### Phase 2: behavior evaluation

- add realistic positive, negative, exceptional, and adversarial workloads;
- use paired, randomized comparisons with holdout cases;
- separate model/service errors from quality failures;
- build a licensed pilot corpus before making cross-type claims.

### Phase 3: open-source validation

- publish small, reproducible releases;
- add local, pytest, promptfoo, and provider adapters where two real uses justify
  a seam;
- recruit external projects and prioritize reported failures over demo counts;
- document reproducible case studies and contribution provenance.

### Phase 4: Codex and OpenAI case study

- support `AGENTS.md` and Codex-style project instructions (synthetic and
  licensed upstream replay pilots committed; nested discovery remains);
- add a current OpenAI adapter for candidate generation, counting, and paired
  evaluation;
- publish a reproducible pull-request report without overwriting source files;
- document exactly how any donated API credits fund open evaluation work.

## Originality boundary

denser may use established ideas such as regression testing, train/holdout
separation, multi-candidate search, compiler-style intermediate
representations, and Pareto selection. Related work must be cited.

Do not copy another project's terminology, prose, examples, fixtures, object
model, configuration schema, return shape, or branded workflow. Reused code or
data requires an explicit license check and attribution. Technical design
independence is not a substitute for trademark, patent, or legal review.
