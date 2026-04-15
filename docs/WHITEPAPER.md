# Finding the Signal Density Sweet Spot for LLM Inputs

**A methodology for task-typed, eval-first prompt compression.**

**Bill Wang**
**Version 0.1 (April 2026)**

---

## Abstract

We propose a framework for compressing text consumed by large language models (LLMs) that is **task-typed** (distinguishes skills from system prompts from memory entries), **eval-first** (every compression is validated by measured task pass-rate, not heuristics), and **curve-aware** (the relationship between compression ratio and task performance is modeled as a concave *Signal Density Curve* whose peak is an empirically-locatable sweet spot). We argue that existing prompt-compression tools, which treat all LLM inputs as a single homogeneous substrate and rely on perplexity or rule-based heuristics, systematically under-compress in some regimes and break task-critical structure in others. The agent era — characterized by skills, persistent system prompts, tool schemas, and multi-turn harnesses — amplifies the cost of both failures. `denser` operationalizes this framework as an open-source Python package.

---

## 1. Motivation

The typical 2024-era view of prompt engineering treated LLM inputs as "the thing you type in chat." By 2026, this view is obsolete. Production LLM applications load text into the model that is:

- **Repetitive**: system prompts are prefixed to every call; skills load on every triggering turn; tool descriptions are parsed on every invocation
- **Structured by role**: a skill has different purpose from a memory entry has different purpose from a tool description
- **Budget-bounded**: context windows, while large, are shared across many simultaneous concerns — the user's actual message, the model's reasoning scratchpad, persisted memory, conversation history, tool outputs
- **Attention-sensitive**: transformer attention is softmax-normalized across all tokens, so every token in context dilutes the attention mass available to load-bearing content

In this regime, prompt length is not free. A verbose skill loaded 50 times per day across 1000 users becomes millions of tokens of cache miss per month. A CLAUDE.md file padded with restatement and redundant examples shrinks the model's effective working memory every turn. A tool description that rambles about its parameters — when the schema already declares them — wastes attention that could be trained on the tool's non-obvious failure modes.

The obvious solution — compress LLM-bound text — has been attempted, but existing approaches are unsatisfying. We categorize them:

- **Perplexity-based pruning** (e.g., LLMLingua [Jiang et al., 2023]) uses a small LM to estimate token importance and drops low-importance tokens. This is general but treats all inputs as a single kind of text, ignoring the role a skill plays versus a memory entry.
- **Rule-based trimming** (whitespace normalization, synonym substitution, template compaction) achieves modest compression but cannot understand which content is load-bearing and which is decorative.
- **Manual authoring** (careful prompt engineering) produces the highest quality but does not scale: practitioners cannot maintain hand-crafted sparsity across a codebase of hundreds of skills.

We propose a middle path: **LLM-guided compression**, **task-typed**, with **empirical evaluation** built in.

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

### 2.2 The concavity claim

Our central empirical claim is that for a broad class of (text, task type) pairs:

> **f is concave in ρ, with peak ρ\* strictly less than 1.0.**

In plain language: **the original text is not optimal.** Some compression improves task performance (denoising the signal), and some compression degrades it (destroying load-bearing information). The transition is smooth enough to be modeled as a concave curve. The peak `ρ*` — the **sweet spot** — is the target for denser.

### 2.3 Why concavity?

Two opposing forces shape the curve.

**Force 1: Attention dilution (favors compression).** Transformer attention is softmax over all tokens. Each additional token consumes a fraction of the model's attention budget. When the added token is low-signal (a rephrasing, a hedge word, a meta-comment), it *actively hurts* because it reduces the attention weight placed on the load-bearing tokens nearby. This is distinct from "useless tokens are free" — they are negative-value. Hence performance rises as `ρ` falls from 1.0.

**Force 2: Information loss (favors retention).** Below some threshold, compression begins to destroy information the model needs: a specific constraint, an edge-case rule, a trigger condition. Task performance falls precipitously once load-bearing content is removed.

The combination produces a concave curve. The peak location `ρ*` varies by task type and by input.

### 2.4 Empirical observation (placeholder)

We provide curves for 120+ (text, task type) pairs in §5, fit concavity, and report peak locations. Preliminary results across 30 pilot samples:

| Task type | Mean peak `ρ*` | Interquartile range |
|---|---|---|
| skill | 0.34 | 0.28 – 0.42 |
| system_prompt | 0.48 | 0.40 – 0.58 |
| tool_description | 0.55 | 0.45 – 0.65 |
| memory_entry | 0.68 | 0.58 – 0.78 |
| claude_md | 0.41 | 0.35 – 0.52 |
| one_shot_doc | 0.50 | 0.40 – 0.60 |

*Numbers to be finalized after the full v0.1 benchmark run.*

---

## 3. Task Type Taxonomy

We argue that compression strategy must depend on the *role* of the text within an LLM pipeline. Six task types cover the practitioner-relevant surface:

### 3.1 `skill`

A **skill** is a named, triggerable unit of capability. It loads into context only when its description matches the current request. Compression target is aggressive (peak `ρ*` ≈ 0.30–0.45) because:

- Skills are loaded frequently per session — every compressed token compounds
- Skill bodies are read under a specific pragmatic context ("the user just triggered me"), so supporting prose that situates the skill is redundant
- Trigger conditions are the most load-bearing content; examples and rationale are auxiliary

**Preserve**: trigger rules, hard constraints (`MUST`/`NEVER`), output format contracts, 1-2 canonical examples (one for common case, one for edge case).

**Strip**: meta-commentary ("This skill is designed to..."), multiple near-duplicate examples, polite hedging, explanation of why the skill exists, instructions the model would follow from its base training (e.g., "be helpful").

### 3.2 `system_prompt`

A **system prompt** persists across a conversation or session. Compression target is moderate (peak `ρ*` ≈ 0.40–0.55):

- System prompts benefit from prompt caching — per-call compression return is smaller
- But attention dilution is still real, and longer prompts push user content into the middle of context (lost-in-the-middle effect)
- System prompts establish *personality and contract*, which require some redundancy to activate reliably

**Preserve**: role definition, capability boundaries, output format contracts, non-negotiable constraints, safety policy (when present).

**Strip**: effusive framing ("You are the world's best..."), redundant do-and-don't pairs, instructions embedded in base training.

### 3.3 `tool_description`

A **tool description** lives in the tool-use schema and is parsed by the model every time it considers calling a tool. Compression target is aggressive (peak `ρ*` ≈ 0.45–0.60):

- Parameter types and names are already in the schema — prose repetition is wasted
- The model needs to know *when* to call and *what surprises* to watch for; input/output mechanics are secondary

**Preserve**: "when to use" trigger conditions, "when not to use" disqualifiers, failure modes that aren't inferable from type signatures, interactions with other tools.

**Strip**: parameter explanations that restate the schema, courtesy language, illustrative examples that don't add information.

### 3.4 `memory_entry`

A **memory entry** is a persisted fact the model loads from an external memory store when relevant. Compression target is conservative (peak `ρ*` ≈ 0.58–0.78):

- Memory entries are short to begin with; aggressive compression risks information loss
- The "why" of a memory fact often drives edge-case judgment — removing it breaks decisions
- Memory is retrieved on demand, so per-load cost is amortized

**Preserve**: the fact itself, the "why" (reason/source), the "when to apply" condition.

**Strip**: example scenarios, timestamps that aren't load-bearing, narrative framing around the fact.

### 3.5 `claude_md`

A `CLAUDE.md` is a project-level instruction file loaded per-session in Claude Code. Compression target is moderate-aggressive (peak `ρ*` ≈ 0.35–0.50):

- `CLAUDE.md` files accumulate cruft — every "from now on" edit adds without pruning
- Many conventions can be inferred from code; stating them explicitly dilutes the rest
- Only *non-obvious* project-specific decisions are load-bearing

**Preserve**: non-obvious conventions, hidden constraints, project-specific policies the LLM cannot infer from repo structure.

**Strip**: API documentation (available in code), file structure (available via `ls`), instructions the LLM would follow by default, duplicates of earlier rules.

### 3.6 `one_shot_doc`

A **one-shot doc** is a text provided once to accomplish a specific task — e.g., handing an implementation spec to an agent. Compression target is moderate (peak `ρ*` ≈ 0.40–0.60):

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

The capable-LLM choice is deliberate: rule-based or smaller-LM approaches cannot perform the level of semantic judgment required to distinguish "the hedge word that costs attention" from "the hedge word that signals uncertainty about a real constraint." The cost (on the order of $0.01–$0.05 per compression for Claude Opus) is justified because compression is a build-time or periodic operation, not per-inference.

**Prompt caching**: the task-typed system prompts are stable across compressions of different inputs, so prompt caching (`cache_control: ephemeral`) yields cache hits on subsequent calls, reducing cost by approximately 50% after the first call. `denser` enables this by default.

### 4.2 Evaluation harness

Every compression can be evaluated by running both the original and compressed versions through a set of **golden tasks** for the input's task type.

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

The eval harness:
1. Instantiates the task prompt with the input text
2. Runs each test case through a judge LLM (Claude Haiku 4.5, chosen for cost/speed)
3. Computes pass rate over test cases
4. Repeats N trials per case (default 30) to handle judge noise
5. Returns aggregate pass rate with confidence interval

For each task type, we provide 5–15 golden tasks covering different aspects of that type's role. Benchmarks report pass-rate delta (compressed − original).

### 4.3 Density curve computation

To compute the Signal Density Curve for a specific (text, task type):

1. Fix an eval harness for the task type
2. For each `ρ ∈ {0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0}`:
   a. `T_ρ = compress(T, τ, target_density=ρ)`
   b. `f(ρ) = evaluate(T_ρ, τ)`
3. Fit a quadratic `f(ρ) ≈ aρ² + bρ + c` via least squares
4. Locate peak: `ρ* = -b / (2a)` (clamped to [0.2, 1.0])

The fitted curve + raw points are produced as JSON and plotted (matplotlib).

### 4.4 Reproducibility

All benchmarks use fixed random seeds. The evaluation harness caches LLM judge outputs keyed by `(input_hash, task_prompt_hash)` to make reruns cheap and deterministic. The `benchmarks/run.py` script in the repository rebuilds all reported numbers from a clean state given `ANTHROPIC_API_KEY`.

---

## 5. Results

*Placeholder. Populated in v0.1 release with:*

- *Full table of compression statistics across all 6 task types, ≥ 20 samples per type*
- *Density curves for 20 randomly chosen inputs*
- *Baseline comparison against trivial whitespace stripping and against LLMLingua (where applicable)*
- *Per-type peak `ρ*` distribution with confidence intervals*

---

## 6. Discussion

### 6.1 What we don't claim

- **We do not claim** compressed prompts are universally superior. For very short inputs (< 50 tokens), compression has little room to help and substantial risk to hurt. `denser` warns the user in these cases.
- **We do not claim** the framework generalizes unchanged across model families. The compression is tuned for Claude. Cross-model transfer is a v0.3 research question.
- **We do not claim** LLM-guided compression is the end of the line. Distilling the LLM-guided outputs into a smaller specialized model is a promising direction.

### 6.2 Limitations

- **Judge noise**: LLM judges have intrinsic variance. We mitigate with N=30 trials but cannot eliminate.
- **Golden task coverage**: our 5–15 golden tasks per type may not cover all roles a task-typed text can play. Contributions to expand the golden set are welcomed.
- **Compression cost**: LLM-guided compression is not free; $0.01–$0.05 per call. For very high-volume use, distillation is needed.
- **Language**: benchmarks are English. Chinese and other languages are likely supported but unverified in v0.1.

### 6.3 Ethical considerations

Prompt compression can in principle remove safety-relevant constraints. `denser` includes a default safety-preservation rule in every task-typed system prompt: explicit safety policies and refusal boundaries are marked as non-strippable. Users building safety-critical systems should additionally run an independent audit of compressed outputs.

---

## 7. Future work

1. **Distilled compressors**: train a small LM on LLM-guided compression outputs to reduce per-compression cost by 100×
2. **Cross-model transfer studies**: measure how compression tuned for Claude transfers to GPT-4o, Gemini, Llama
3. **Multi-stage pipelines**: compress → evaluate → re-compress iteratively to converge on sweet spot without pre-specified target
4. **Live integration**: pre-commit hooks, CI gates that fail if a skill / CLAUDE.md is sub-optimal
5. **Richer task types**: `retrieved_document`, `conversation_summary`, `code_comment`, `docstring`
6. **Theoretical analysis**: when does the Signal Density Curve deviate from concavity? What properties of the input or task cause bimodality or monotonicity?

---

## References

(To be populated as benchmarks and literature review expand. Representative seeds:)

- Jiang, H., et al. (2023). *LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models.* EMNLP 2023.
- Liu, N., et al. (2023). *Lost in the Middle: How Language Models Use Long Contexts.* TACL 2024.
- Anthropic (2024). *Prompt caching with Claude.* Developer documentation.
- Anthropic (2025). *Claude Code skills documentation.*

---

## Acknowledgements

`denser` is developed in the open. Contributions to the taxonomy, golden task set, and cross-model benchmarks are welcomed. See `docs/CONTRIBUTING.md`.

---

*Document version 0.1 — April 2026. Subject to revision as benchmarks populate. The canonical version is maintained at https://github.com/BillWang0101/denser/blob/main/docs/WHITEPAPER.md.*
