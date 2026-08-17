# Testing Signal Density in LLM Instruction Assets

**A methodology for task-typed, eval-first prompt compression.**

**Bill Wang**
**Version 0.1 (April 2026)**

> **Research status (August 2026): hypothesis, not validated result.** The
> original draft stated planned benchmark counts and a concavity claim more
> strongly than the committed evidence supports. Those claims are withdrawn
> pending asset-specific behavior tests and reproducible results. The active
> product and evidence design is in [`DESIGN.md`](DESIGN.md).

---

## Abstract

This note proposes role-aware refactoring for version-controlled LLM
instruction assets. It treats shorter text as a candidate to verify, not an
automatic improvement. The original Signal Density Curve is retained as a
testable visualization hypothesis: observed quality may be concave, monotone,
flat, noisy, multi-peaked, or maximized by the original. The implementation is
an alpha prototype whose built-in fixtures currently check structure rather
than establish behavioral equivalence.

---

## 1. Motivation

The typical 2024-era view of prompt engineering treated LLM inputs as "the thing you type in chat." By 2026, this view is obsolete. Production LLM applications load text into the model that is:

- **Repetitive**: system prompts are prefixed to every call; skills load on every triggering turn; tool descriptions are parsed on every invocation
- **Structured by role**: a skill has different purpose from a memory entry has different purpose from a tool description
- **Budget-bounded**: context windows, while large, are shared across many simultaneous concerns — the user's actual message, the model's reasoning scratchpad, persisted memory, conversation history, tool outputs
- **Attention-sensitive**: long-context behavior can vary with content,
  position, model, and workload; additional text may help, hurt, or have no
  measurable effect

In this regime, prompt length is not free, but its economic and behavioral cost
must be measured separately. Prompt caching may reduce repeated-prefix cost
without reducing active context. A rewrite is useful only when its generation,
maintenance, and regression risk are justified by observed workload results.

The obvious solution — compress LLM-bound text — has been attempted, but existing approaches are unsatisfying. We categorize them:

- **Perplexity-based pruning** (e.g., LLMLingua [Jiang et al., 2023]) uses a small LM to estimate token importance and drops low-importance tokens. This is general but treats all inputs as a single kind of text, ignoring the role a skill plays versus a memory entry.
- **Rule-based trimming** (whitespace normalization, synonym substitution, template compaction) achieves modest compression but cannot understand which content is load-bearing and which is decorative.
- **Manual authoring** (careful prompt engineering) produces the highest quality but does not scale: practitioners cannot maintain hand-crafted sparsity across a codebase of hundreds of skills.

We propose a narrower workflow: role-aware candidate generation with explicit
preservation contracts and asset-specific regression tests.

---

## 2. The Signal Density Curve

### 2.1 Definition

Let `T` be a text, `τ` a task type (e.g., `skill`, `system_prompt`; see §3), and `ρ ∈ (0, 1]` a target compression ratio defined as:

```
ρ = |compress(T, τ, ρ)| / |T|
```

(both sides measured in LLM tokens). Let `E(T, τ)` be a scoring function — the *evaluation harness* described in §4.2 — that measures how well `T` performs on a golden task set for task type `τ`, returning a pass-rate in `[0, 1]`.

The **Signal Density Curve** of a (text, task type) pair is the function:

```
f_{T, τ}(ρ) = E(compress(T, τ, ρ), τ)
```

### 2.2 The original concavity hypothesis

The original draft proposed the following hypothesis for a broad class of
(text, task type) pairs:

> **H1: f is concave in ρ, with peak ρ\* strictly less than 1.0.**

The repository does not currently establish H1. The original may be best, and
the observations may be non-concave. denser therefore treats the original as a
candidate and selects only among versions that pass hard behavior gates.

### 2.3 Why test density at all?

Two possible forces motivate a density sweep, without determining its shape.

**Redundancy removal may help.** Repetition, hedging, and stale guidance can
increase cost or obscure important rules for some models and workloads.

**Information loss may hurt.** Rewriting can remove a constraint, edge case,
trigger, source, or useful redundancy. Harm may be abrupt or visible only in a
rare case.

Their interaction is an empirical question for each asset, workload, and model.

### 2.4 Current evidence

The repository contains eight before/after examples and eleven built-in
structural fixture files. It does not contain a 30-sample pilot, 120 evaluated
pairs, confidence intervals, or evidence of a cross-asset density optimum. The
ranges in §3 are exploratory generation defaults inherited from the original
design and must not be cited as observed performance peaks.

---

## 3. Task Type Taxonomy

We argue that compression strategy must depend on the *role* of the text within an LLM pipeline. Six task types cover the practitioner-relevant surface:

### 3.1 `skill`

A **skill** is a named, triggerable unit of capability. It loads into context
only when its description matches the current request. The current aggressive
candidate-generation range is 0.30–0.45; this is a working prior, not a measured
peak.

- Skills are loaded frequently per session — every compressed token compounds
- Skill bodies are read under a specific pragmatic context ("the user just triggered me"), so supporting prose that situates the skill is redundant
- Trigger conditions are the most load-bearing content; examples and rationale are auxiliary

**Preserve**: trigger rules, hard constraints (`MUST`/`NEVER`), output format contracts, 1-2 canonical examples (one for common case, one for edge case).

**Strip**: meta-commentary ("This skill is designed to..."), multiple near-duplicate examples, polite hedging, explanation of why the skill exists, instructions the model would follow from its base training (e.g., "be helpful").

### 3.2 `system_prompt`

A **system prompt** persists across a conversation or session. The current
moderate candidate-generation range is 0.40–0.55 and remains unvalidated as an
optimum:

- System prompts benefit from prompt caching — per-call compression return is smaller
- But attention dilution is still real, and longer prompts push user content into the middle of context (lost-in-the-middle effect)
- System prompts establish *personality and contract*, which require some redundancy to activate reliably

**Preserve**: role definition, capability boundaries, output format contracts, non-negotiable constraints, safety policy (when present).

**Strip**: effusive framing ("You are the world's best..."), redundant do-and-don't pairs, instructions embedded in base training.

### 3.3 `tool_description`

A **tool description** lives in the tool-use schema and is parsed by the model
when it considers calling a tool. The current candidate-generation range is
0.45–0.60 and remains exploratory:

- Parameter types and names are already in the schema — prose repetition is wasted
- The model needs to know *when* to call and *what surprises* to watch for; input/output mechanics are secondary

**Preserve**: "when to use" trigger conditions, "when not to use" disqualifiers, failure modes that aren't inferable from type signatures, interactions with other tools.

**Strip**: parameter explanations that restate the schema, courtesy language, illustrative examples that don't add information.

### 3.4 `memory_entry`

A **memory entry** is a persisted fact the model loads from an external memory
store when relevant. The current conservative candidate-generation range is
0.58–0.78 and remains exploratory:

- Memory entries are short to begin with; aggressive compression risks information loss
- The "why" of a memory fact often drives edge-case judgment — removing it breaks decisions
- Memory is retrieved on demand, so per-load cost is amortized

**Preserve**: the fact itself, the "why" (reason/source), the "when to apply" condition.

**Strip**: example scenarios, timestamps that aren't load-bearing, narrative framing around the fact.

### 3.5 `claude_md`

A `CLAUDE.md` is one example of a project-level instruction file. The current
moderate-aggressive candidate-generation range is 0.35–0.50 and remains
exploratory. The active design generalizes this role to files such as
`AGENTS.md` rather than treating one vendor filename as the domain model.

- `CLAUDE.md` files accumulate cruft — every "from now on" edit adds without pruning
- Many conventions can be inferred from code; stating them explicitly dilutes the rest
- Only *non-obvious* project-specific decisions are load-bearing

**Preserve**: non-obvious conventions, hidden constraints, project-specific policies the LLM cannot infer from repo structure.

**Strip**: API documentation (available in code), file structure (available via `ls`), instructions the LLM would follow by default, duplicates of earlier rules.

### 3.6 `one_shot_doc`

A **one-shot doc** is a text provided once to accomplish a specific task — e.g.,
handing an implementation spec to an agent. The current moderate
candidate-generation range is 0.40–0.60 and remains exploratory:

- One-shot docs are used once; amortized cost is low
- But they are *executed* by the LLM, so instruction clarity is paramount
- Retained structure (headers, lists) helps the LLM organize execution

**Preserve**: actionable instructions, decision criteria for judgment calls, acceptance criteria, edge-case handling.

**Strip**: motivational preamble, background context already implied by the task, summaries of what will be said.

### 3.7 Why these six?

The taxonomy covers the practitioner-relevant inputs as of April 2026. Additional types (e.g., `retrieved_document`, `conversation_summary`) are natural extensions and are roadmap for v0.3. We avoid over-taxonomizing in v0.1 — the six we include each has a distinct compression strategy; adding a seventh would risk redundancy with existing types.

---

## 4. Methodology

### 4.1 LLM-guided compression

`denser` produces a compressed text by delegating to a capable LLM (Claude Opus 4.6 by default), given:

- The original text
- A task-typed **system prompt** that encodes the preserve/strip rules for that task type
- A **target density** `ρ_target` expressed as a fraction of original tokens
- An instruction to also produce a **rationale** describing what was removed and why

The current prototype uses a capable LLM because semantic rewrites require
judgment. The repository does not yet contain a controlled comparison proving
that a particular model class is necessary or cost-optimal.

**Prompt caching**: the Anthropic adapter marks the stable system block for
caching. Actual cache eligibility, hits, latency, and cost depend on provider,
model, prefix size, order, and timing, and must be measured from provider usage
data. Caching changes economic cost but not active-context length.

### 4.2 Evaluation harness

Original and candidate text can be compared with the same task definitions. The
bundled fixtures currently test structural properties. Behavioral claims
require asset-specific workloads that exercise real triggers, constraints,
tool calls, outputs, and exceptional paths.

A golden task consists of:

- A **task prompt** that tests whether the input text successfully performs its intended role
- A set of **test cases** with expected outputs
- A **pass threshold** (e.g., 0.9)

Example (skill trigger accuracy):

```yaml
task_type: skill
prompt_slot: <the-skill-text>
task_prompt: |
  Given the following skill definition, would it trigger
  on the user request? Answer yes/no.

  Skill:
  <input>

  User request: "{request}"
test_cases:
  - request: "please review my PR"
    expected: "yes"
  - request: "what is 2+2"
    expected: "no"
pass_threshold: 0.9
```

The current eval harness:
1. Instantiates the task prompt with the input text
2. Runs each test case through a judge LLM (Claude Haiku 4.5, chosen for cost/speed)
3. Computes pass rate over test cases
4. Repeats N trials per case when requested (default 1)
5. Returns observed aggregate pass rates without a confidence interval

The repository currently provides one to three structural fixture files per
task type, eleven files total. Their pass-rate delta is not a behavioral
equivalence result.

### 4.3 Density curve computation

To compute the Signal Density Curve for a specific (text, task type):

1. Fix an eval harness for the task type
2. For each `ρ ∈ {0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0}`:
   a. `T_ρ = compress(T, τ, target_density=ρ)`
   b. `f(ρ) = evaluate(T_ρ, τ)`
3. Optionally fit a descriptive quadratic `f(ρ) ≈ aρ² + bρ + c`
4. If the fit is concave, report its clamped vertex; otherwise report the best
   raw point

The fitted curve and raw points can be produced as JSON and plotted. The result
is exploratory and does not prove concavity or identify a production-safe
optimum.

### 4.4 Reproducibility

The current runner records model identifiers and trial count when JSON output is
requested. It does not currently control provider randomness, cache judge
outputs, calculate confidence intervals, or rebuild any general performance
table in the README. Reproducible publication requires committed inputs,
behavior tasks, raw results, model/settings, provenance, and a reproduction
command.

---

## 5. Results

No general performance results are published. The eight bundled examples are
worked demonstrations and the cross-model note is a single-input observation.
They are useful for developing hypotheses, not for estimating average savings,
behavior change, density peaks, or model rankings.

---

## 6. Discussion

### 6.1 What we don't claim

- **We do not claim** a shorter instruction is better. The original may be the
  only passing candidate.
- **We do not claim** the exploratory density ranges are observed optima.
- **We do not claim** built-in structural checks establish behavior
  preservation.
- **We do not claim** results transfer unchanged across assets, languages,
  models, provider versions, tool sets, or cache configurations.

### 6.2 Limitations

- **Judge validity and noise**: the current harness treats model answers as
  pass/fail observations and does not calibrate a judge against human labels.
- **Fixture coverage**: bundled fixtures are generic structural checks, not
  asset-specific workloads.
- **Operational errors**: current reports do not yet separate judge/provider
  failures from content failures.
- **Counting**: the local estimator is not a provider-rendered token count.
- **Corpus**: eight examples are insufficient for cross-type conclusions.
- **Language**: examples include English and limited Chinese material, without
  a controlled multilingual evaluation.

### 6.3 Ethical considerations

Prompt compression can in principle remove safety-relevant constraints. `denser` includes a default safety-preservation rule in every task-typed system prompt: explicit safety policies and refusal boundaries are marked as non-strippable. Users building safety-critical systems should additionally run an independent audit of compressed outputs.

---

## 7. Future work

1. **Preservation contracts**: extract obligations with source spans and test coverage.
2. **Evidence reports**: connect each deletion or rewrite to a diff, test, and rollback path.
3. **Behavior replay**: paired, randomized comparisons on asset-specific and holdout cases.
4. **Provider-aware accounting**: separate estimated text length, rendered input,
   active context, and cache economics.
5. **Cross-model studies**: publish transfer results only with committed raw data
   and negative cases.
6. **Theory testing**: test concavity rather than assuming it, and report
   monotone, flat, noisy, or multi-modal observations.

---

## References

(Representative references; the related-work review will expand with the
behavior-evaluation implementation.)

- Jiang, H., et al. (2023). *LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models.* EMNLP 2023.
- Liu, N., et al. (2023). *Lost in the Middle: How Language Models Use Long Contexts.* TACL 2024.
- Anthropic (2024). *Prompt caching with Claude.* Developer documentation.
- Anthropic (2025). *Claude Code skills documentation.*

---

## Acknowledgements

`denser` is developed in the open. Contributions to the taxonomy, golden task set, and cross-model benchmarks are welcomed. See `docs/CONTRIBUTING.md`.

---

*Document version 0.1 — April 2026; evidence-status correction August 2026. The canonical version is maintained at https://github.com/Evostructs/denser/blob/main/docs/WHITEPAPER.md.*
