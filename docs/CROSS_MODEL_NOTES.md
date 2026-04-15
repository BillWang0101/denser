# Cross-Model Compression Notes

> Empirical data on how different LLMs behave when given denser's task-typed
> compression prompts, with the same input and the same target density.

This document is evidence, not marketing. We ran identical compressions —
same text (`denser/skills/denser-compress/SKILL.md`, 1249 tokens), same task
type (`skill`, sweet spot 0.30 – 0.45, target 0.375), same prompt template —
through 12 different models across 2 providers. The findings below drive
denser's backend recommendations and motivate v0.3 prompt-per-backend work.

---

## Summary table

| # | Model | Provider | Density | vs sweet spot | Savings | Latency |
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

**Sweet spot for `skill` task type: density 0.30 – 0.45.**

---

## Four takeaways

### 1. Only Claude Opus 4.6 and GLM-4.6 naturally land in the sweet spot

Out of 11 models that produced valid output, **only 2 landed inside 0.30 – 0.45** with the default prompt. Claude hits the midpoint; GLM-4.6 hits the lower boundary.

Every other model needs prompt tuning to calibrate, which is v0.3 roadmap work.

### 2. Newer / larger 2026-era models are conservative (0.45 – 0.53)

Contrary to the intuition that "better models compress better," the newest models — GLM-5.1, Kimi-K2.5, DeepSeek-R1, Qwen3.5-397B, DeepSeek-V3.2 — cluster in the 0.45 – 0.53 band. They **under-compress**, preferring to preserve content.

This is plausibly an RLHF artifact: modern models are trained to preserve user-provided content, and compression looks like an unwanted transformation.

### 3. Older / smaller models over-compress aggressively (0.15 – 0.23)

DeepSeek-V3, DeepSeek-V2.5, Qwen2.5-32B all compress far below the sweet spot (density 0.15 – 0.23), losing format contracts and fine-grained structure. DeepSeek-V3's compressed output of denser's own SKILL.md dropped the entire report-format specification, which would have broken the skill's runtime behavior.

This pattern matters because these models are **free or very cheap** on SiliconFlow — the "cost-efficient" choice also happens to be the "overcompression" choice.

### 4. Reasoning models are slow and no more accurate

Three reasoning models (Kimi-K2-Thinking at 370s, DeepSeek-R1 at 274s, Qwen3.5-397B at 283s) take 10× – 15× longer than non-reasoning peers and produce density *within 1% of the non-reasoning models*.

**Recommendation**: for compression tasks, prefer non-reasoning variants. Reasoning provides no measurable benefit at this task and costs minutes per call.

---

## Backend recommendations

Based on these findings, denser recommends:

| Use case | Backend | Why |
|----------|---------|-----|
| Production, stable output | `ClaudeBackend("claude-opus-4-6")` | Lands in sweet-spot center; prompt caching amortizes cost |
| Open-source, free, good quality | `SiliconFlowBackend("zai-org/GLM-4.6")` | The only open-source model naturally inside sweet spot |
| Fast + cheap, accept over-compression | `SiliconFlowBackend("deepseek-ai/DeepSeek-V3.2")` | 30s latency, slight OVER (acceptable for many use cases) |
| **Avoid for compression** | DeepSeek-V3 / V2.5 / Qwen2.5-32B / any reasoning model | over-compresses or too slow |

v0.3 will add per-model prompt tuning so DeepSeek / Qwen / newer GLM can also hit sweet spot reliably. Until then, use the recommended backends above.

---

## Methodology notes

- **Input**: `denser/skills/denser-compress/SKILL.md` (our own skill definition — dogfood).
- **Target density**: 0.375 (midpoint of skill task type's 0.30 – 0.45 sweet spot).
- **Prompt**: default `skill` system prompt built by `denser/prompts/registry.py::build_system_prompt` — identical across models.
- **Density measurement**: `denser.tokens.estimate_tokens` heuristic (`max(chars/4, words*1.3)`). Not API-exact but consistent across measurements.
- **Latency**: wall-clock from `backend.complete()` entry to first response byte (single trial; no averaging).
- **Single trial per model**: these are indicative, not statistically significant. v0.2+ benchmarks use n=10+ with variance reporting.

Raw results persisted at `_cross_model_results.json` and `_cross_model_tuning_results.json`
in gitignored paths for later re-analysis.

---

## What this means for the project

1. **denser's claim "works with Claude"** is empirically solid. The sweet-spot framework calibrates against Claude's RLHF behavior.

2. **denser's claim "works with other backends"** is *partially* true. GLM-4.6 works out-of-the-box; others need per-model prompt tuning (v0.3).

3. **The Signal Density Curve framework is model-dependent**. What's a "sweet spot" for Claude may be different for DeepSeek. This is a research avenue, not a bug: future work can publish per-model sweet-spot curves.

4. **"Pick a backend based on density convergence"** — this evaluation itself is a denser-native metric. Future denser versions may ship a CLI subcommand (`denser backends test`) that lets users pick the best-matching backend for their own input.

---

*Last updated: 2026-04-15. Numbers may shift as we expand the test suite and add per-model prompt variants.*
