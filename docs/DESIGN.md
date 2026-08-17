# denser design direction

Status: active design for the next development cycle. This document supersedes
the product claims in the original four-week launch plan.

## Product promise

denser audits whether a versioned LLM context change preserves required
behavior, and whether the workload used for that conclusion can detect a
known-bad change.

The proposed variant may be a rewrite, selective-load result, manually produced
summary, or exported runtime-compaction snapshot. denser does not need to
produce the variant. It provides the evidence layer that decides whether the
observed behavior stayed stable.

Shorter text is not automatically better. Equal baseline/variant scores are
also not automatically evidence: without a sensitive negative control, the
result remains inconclusive.

## Scope

The first stable release focuses on textual, reviewable context snapshots:

- system and developer instructions;
- skills and triggerable procedures;
- tool descriptions and tool-selection rules;
- project instructions such as `AGENTS.md` and `CLAUDE.md`;
- persistent memory rules;
- one-shot implementation or research briefs.

The first release can audit before/after text exported by another compactor,
but it does not implement a provider's runtime conversation compaction. Hidden
vectors, model KV-cache optimization, and inaccessible host/system prefixes
remain out of scope. RAG and task-conditioned loading may be audited once their
selected textual context is captured reproducibly.

## Core workflow

The public workflow should remain small, with `audit` as the deep interface:

1. Define behavior cases for the baseline and a known-bad negative control that
   should fail at least one case.
2. `audit` replays the baseline, proposed variant, and negative control. It
   reports `preserved` only when the variant matches every covered baseline
   outcome and the workload catches the negative control.
3. Rerun `audit` after the context, model, runtime configuration, or workload
   changes. Compare provider-reported full input usage, not only file length.

`inspect` can build a preservation contract. `optimize` and `compress` can
propose variants. `replay` is the lower-level execution runner. `eval` and
`curve` remain experimental. None of these candidate-generation paths can
substitute for an audit verdict.

Current implementation status: `audit_context` and `denser audit` are available
as report schema `denser.context-audit/v1`. They consolidate paired replay,
case-level regression detection, negative-control sensitivity, asset-only token
estimates, and provider-reported end-to-end input totals. A variant improvement
is sent to review rather than silently classified as preservation; operational
errors and undetected controls fail closed as inconclusive.

The Codex CLI adapter also exposes a narrowly scoped `text-only` capability
profile. It is for pre-bundled text decisions only and removes unused tool and
extension context. In a seeded randomized audit with three trials per case,
both profiles passed every covered case across 84 calls, with no operational
errors or transport fallbacks. The two workloads reduced provider-reported
input per call by 10.55% and 10.60%. This is the first result to clear the
project's two-scenario, 10% end-to-end gate; it does not apply to coding or
other tasks that require those capabilities. The first strict run caught one
missing output-contract behavior, which was fixed as the versioned
`text-only/v1` wrapper before rerunning the complete audit.

The supporting `inspect`, `verify`, and multi-candidate
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

Verification has four layers:

1. **Structural checks** validate protected literals, schemas, references, and
   other deterministic invariants. The current built-in fixtures belong here.
2. **Behavior replay** runs the original and each candidate against the same
   realistic workload and target execution model.
3. **Holdout and adversarial checks** cover near-miss triggers, conflicting
   rules, exceptional paths, and prompt injection that candidate generation did
   not see.
4. **Sensitivity controls** run a known-bad context mutation. If the workload
   cannot detect that mutation, observed baseline/variant parity is
   inconclusive.

Deterministic assertions take priority over model judges. Model errors are
reported separately from content failures. Candidate selection and final
reporting use different cases to reduce overfitting.

## Variant selection

denser does not assume that quality is a concave function of compression ratio.
It records observed candidates and selects only among candidates that pass all
hard gates. Candidate generation may prefer a shorter variant, but `audit`
considers behavior evidence first and accepts variants that were produced by
other systems. A future selector may expose a Pareto set when active context,
behavior, latency, cost, readability, or diff size trade off.

The Signal Density Curve remains an experimental visualization of observed
points. A quadratic fit is descriptive only and is never proof of a universal
sweet spot.

## Evidence report

Every audit should eventually return:

- the baseline, proposed variant, and negative-control identities;
- a preservation contract;
- a diff;
- a ledger marking each source unit as kept, merged, rewritten, externalized,
  or rejected for removal;
- the tests covering each change;
- model, tokenizer/counting method, settings, cost, latency, and timestamp;
- operational errors and uncovered risks;
- enough provenance to reproduce or roll back the result.

Asset-only estimates and provider-reported full input usage must remain
separate fields. Missing runtime usage is reported as unavailable, never
replaced silently with a local estimate.

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

### Phase 3: context behavior audit

- consolidate replay, negative-control sensitivity, and token measurements
  behind `audit_context` and `denser audit`;
- fail closed when a control is absent, undetected, or affected by operational
  errors;
- keep asset-only length and provider-reported full input as separate metrics;
- add long-horizon cases that cross a real runtime-compaction event.

### Phase 4: selective loading and compaction fidelity

- capture reproducible before/after textual context snapshots from real agent
  runtimes without duplicating their compaction implementation;
- test permissions, user decisions, unfinished work, and failure recovery after
  compaction;
- compare whole-context rewriting with task-conditioned loading;
- require meaningful end-to-end savings before making cost or latency claims.

### Phase 5: open-source validation

- publish small, reproducible releases;
- add local, pytest, promptfoo, and provider adapters where two real uses justify
  a seam;
- recruit external projects and prioritize reported failures over demo counts;
- document reproducible case studies and contribution provenance.

### Completed pilot: Codex and OpenAI project instructions

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
