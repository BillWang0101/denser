# Cross-Model Compression Notes

> Empirical data on how different LLMs behave when given denser's task-typed
> compression prompts, with the same input and the same target density.

This is a single-input exploratory note, not a backend benchmark or production
recommendation. We ran identical compressions —
same text (`denser/skills/denser-compress/SKILL.md`, 1249 tokens), same task
type (`skill`, exploratory range 0.30 – 0.45, target 0.375), same prompt template —
through 12 different models across 2 providers. The findings below drive
denser's backend recommendations and motivate v0.3 prompt-per-backend work.

---

## Summary table

| # | Model | Provider | Density | vs working range | Savings | Latency |
|---|-------|----------|--------:|---------------|--------:|--------:|
| 1 | `claude-opus-4-6` | Anthropic | **0.42** | ✓ IN (center) | 58% | ~20s |
| 2 | `zai-org/GLM-4.6` | SiliconFlow | **0.32** | ✓ IN (lower) | 68% | 61s |
| 3 | `Pro/zai-org/GLM-5.1` | SiliconFlow | 0.452 | slight OVER | 55% | 72s |
| 4 | `Pro/moonshotai/Kimi-K2.5` | SiliconFlow (reasoning) | 0.467 | slight OVER | 53% | **370s** |
| 5 | `deepseek-ai/DeepSeek-R1` | SiliconFlow (reasoning) | 0.464 | slight OVER | 54% | 274s |
| 6 | `Qwen/Qwen3.5-397B-A17B` | SiliconFlow | 0.460 | slight OVER | 54% | 283s |
| 7 | `deepseek-ai/DeepSeek-V3.2` | SiliconFlow | 0.525 | OVER | 48% | 30s |
| 8 | `Qwen/Qwen2.5-72B-Instruct` | SiliconFlow | 0.536 | OVER | 46% | 27s |
| 9 | `deepseek-ai/DeepSeek-V3` | SiliconFlow | 0.208 | ✗ UNDER | 79% | 36s |
| 10 | `Qwen/Qwen2.5-32B-Instruct` | SiliconFlow | 0.229 | ✗ UNDER | 77% | 12s |
| 11 | `deepseek-ai/DeepSeek-V2.5` | SiliconFlow | 0.147 | ✗ UNDER | 85% | 22s |
| 12 | `Qwen/Qwen3.5-122B-A10B` | SiliconFlow | ERR: empty content | — | — | — |
| 13 | `stepfun-ai/Step-3.5-Flash` | SiliconFlow | ERR: empty content | — | — | — |

**The comparison used denser's exploratory `skill` target range: 0.30 – 0.45.**
The repository does not currently establish this range as a behavior optimum.

---

## Four takeaways

### 1. Two outputs landed in the working range on this input

Out of 11 models that produced valid output, **only 2 landed inside 0.30 – 0.45** with the default prompt. Claude hits the midpoint; GLM-4.6 hits the lower boundary.

This does not show that other models need prompt tuning in general; it shows
that one prompt produced different output lengths across one generation per
model.

### 2. Newer / larger 2026-era models are conservative (0.45 – 0.53)

On this input, GLM-5.1, Kimi-K2.5, DeepSeek-R1, Qwen3.5-397B, and
DeepSeek-V3.2 returned densities in the 0.45–0.53 band, above the exploratory
target range.

One possible explanation is training that favors preserving user-provided
content, but this run does not identify a cause.

### 3. Older / smaller models over-compress aggressively (0.15 – 0.23)

DeepSeek-V3, DeepSeek-V2.5, and Qwen2.5-32B produced densities 0.15–0.23,
below the working range. DeepSeek-V3's candidate dropped the report-format
specification, a structural regression that requires rejection. Runtime impact
was not measured in an asset-specific behavior suite.

Provider pricing changes over time and was not part of this evaluation.

### 4. Reasoning models were slower in this single run

Three reasoning-model runs were among the slowest observations: 274–370
seconds in this environment. Single runs with different providers and models
do not isolate reasoning as the cause.

No accuracy comparison was run: the note records density and a manual content
observation, not an asset-specific behavior suite. The latency figures motivate
a controlled follow-up; they do not justify a general model recommendation.

---

## Behavior-replay follow-up — official DeepSeek API, 2026-08-17

A separate follow-up used the official DeepSeek API model IDs
`deepseek-v4-pro` and `deepseek-v4-flash`. Each report used three trials, seed
`20260817`, and explicit non-thinking mode. Replay answers are short exact
labels with a 128-token output bound, so disabling provider reasoning reserves
the bound for the scored answer. An earlier reasoning-enabled diagnostic was
excluded because several calls exhausted that allowance before producing final
content.

| Workload | V4 Pro | V4 Flash |
|---|---:|---:|
| Synthetic release operations, original | 27/27 | 27/27 |
| Synthetic release operations, candidate | 27/27 | 25/27 |
| Public holdout, original, 22 valid cases | 66/66 | 63/66 |
| Public holdout, candidate, 22 valid cases | 66/66 | 63/66 |
| Neutral policy mutant, source → mutant | 15/15 → 9/15 | 15/15 → 6/15 |
| Permission-causal source suite, original | 15/15 | 12/15 |
| Permission-causal source suite, candidate | 15/15 | 12/15 |

All 534 calls completed without an operational error. One known holdout case
was excluded from the valid-case rows because its exact scorer expects
`allowed-failure-prerelease`, while the source says `allowed-failure
prerelease`. The immutable raw reports and their hashes are bound by the
[cross-model audit](../examples/project_instructions/deepseek-v4-replay-audit.2026-08-17.json).

On these workloads, V4 Pro followed the exact-label permission boundaries more
consistently. V4 Flash still matched the original and candidate on the same 63
of 66 valid public-holdout observations, but both assets made the same three
errors on one critical permission case. The synthetic candidate also varied on
one adversarial case. The neutral mutant degraded under both models, confirming
material but incomplete control sensitivity.

Two additional reports keep the source instruction unchanged while reversing
only the expected labels. They are consistency diagnostics, not runs of the
counterfactual instruction and not causal evidence about an instruction
intervention. The adapter did not record provider token usage, so this follow-up
does not make a cost claim.

These results apply only to the committed assets, suites, model IDs, settings,
and date. They do not establish a general model ranking.

---

## Observed outputs (not backend recommendations)

The recorded observations are:

| Observation | Backend | What happened on this input |
|----------|---------|-----|
| Inside working range | `ClaudeBackend("claude-opus-4-6")` | Density 0.42 in one run |
| Inside working range | `SiliconFlowBackend("zai-org/GLM-4.6")` | Density 0.32 in one run |
| Outside working range | Other tested outputs | Length and latency varied; behavior was not systematically evaluated |

Future work should repeat generations, run asset-specific behavior cases, and
separate model/service failures from content failures before recommending a
backend.

---

## Methodology notes

- **Input**: `denser/skills/denser-compress/SKILL.md` (our own skill definition — dogfood).
- **Target density**: 0.375 (midpoint of the exploratory skill range 0.30–0.45).
- **Prompt**: default `skill` system prompt built by `denser/prompts/registry.py::build_system_prompt` — identical across models.
- **Density measurement**: `denser.tokens.estimate_tokens` heuristic (`max(chars/4, words*1.3)`). Not API-exact but consistent across measurements.
- **Latency**: wall-clock from `backend.complete()` entry to first response byte (single trial; no averaging).
- **Single trial per model**: these are indicative, not statistically
  significant. Repeated trials with variance reporting remain future work.

The raw outputs were retained only in gitignored local experiment files and are
not part of this repository. The table therefore cannot serve as an
independently auditable public benchmark.

---

## What this means for the project

1. **The current rewrite prompt produced a plausible Claude candidate on this
   input.** That is a demo observation, not a general behavior result.

2. **The OpenAI-compatible adapter returned outputs from several backends.**
   Output length alone does not establish that a backend works correctly.

3. **Candidate behavior may be model-dependent.** Future work should publish raw
   observations, holdout tests, and non-concave or original-wins cases.

4. **Do not pick a backend from density convergence alone.** Select with real
   behavior, cost, latency, and reproducibility measurements.

---

*Last updated: 2026-08-17. Numbers may shift as we expand the test suite and add per-model prompt variants.*
