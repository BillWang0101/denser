# Case study: compressing a real Chinese-language skill with GLM-4.6

> The first non-Claude, non-English, non-self-generated compression case in the
> denser benchmark suite. GLM-4.6 via SiliconFlow compressed a 1432-token
> Chinese academic-persona skill to 627 tokens, landing **inside the skill
> sweet spot** with no prompt tuning.

---

## What was compressed

`luming/SKILL.md` — a Claude Code skill that makes Claude embody Shanghai Jiao Tong University professor Lu Ming's analytical voice for discussions of Chinese urban economics, migration, hukou reform, and empirical research methodology.

- **Source**: the user's real `~/.claude/skills/luming/SKILL.md`
- **Language**: Chinese (Simplified), with English technical terms
- **Original**: 1432 tokens, 5728 chars

---

## What denser produced

| | value |
|---|---:|
| Backend | `SiliconFlowBackend("zai-org/GLM-4.6")` |
| Original tokens | 1432 |
| Compressed tokens | 627 |
| Density | **0.438** — inside sweet spot (0.30 – 0.45) |
| Savings | **56%** |
| Latency | 101s |

The backend recommendation from [`docs/CROSS_MODEL_NOTES.md`](../../../docs/CROSS_MODEL_NOTES.md) — "GLM-4.6 is the only open-source model naturally inside the skill sweet spot" — is independently confirmed on this real-world input.

---

## Structural preservation

Running the compressed version against the shipped `skill` golden tasks is not executed here (it would require the judge to read Chinese correctness signals), but a manual inspection confirms each load-bearing category of the taxonomy's Preserve list is present:

| Preserve category | Preserved in compressed? | Evidence |
|---|---|---|
| Trigger conditions | ✓ | First `Trigger:` line lists every topic domain from the original |
| Anti-triggers | ✓ | "If user requests an 'objective' view, acknowledge Lu Ming's views are debated" |
| Hard constraints (MUST/NEVER) | ✓ | "MUST use one of two voices", "NEVER use AI-style transitions..." |
| Output format contracts | ✓ | Template A/B/C output structures preserved |
| Canonical examples | ✓ | Templates A (analyze phenomenon) / B (review paper) / C (advise student) kept |

---

## One surprising observation: GLM-4.6 translated instructions to English

The original skill is written in Chinese. The compressed output is written primarily in **English**, while preserving Chinese-specific concept names intact (陆铭, 户籍, 农民工, etc.) and English technical terminology verbatim ("Baumol's cost disease", "post-industrial services", "reference frame").

This is a **judgment call by the model**, not an explicit instruction. Two interpretations:

1. **Pro-English hypothesis**: GLM decided that LLM-executed instructions work more reliably in English (base-training distribution) while cultural content ideally stays Chinese. The compressed skill still *executes* in Chinese when activated — it embodies Professor Lu's Chinese-language voice — but the *rules* for executing it are in English.

2. **Default-voice hypothesis**: GLM's "compression" mode reverted to its strongest training language regardless of input. This would be a failure mode for anyone who specifically wants their skill instructions in Chinese (e.g., for review by non-English teammates).

A compression that's instructionally valid but changes the input's language is a **partial semantic shift**. The `denser` methodology (Layer 1 question 1: "Does removing this break a downstream decision?") would flag language preservation as load-bearing if the skill were intended for non-English-literate reviewers, but not if it's purely for LLM execution.

**Lesson**: for skills where language of instruction matters, the current denser prompts do not explicitly forbid translation. A future `preserve_language=True` flag or prompt variant would address this. This is added to the v0.3 TODO as a known limitation.

---

## What this case study proves

1. **GLM-4.6 via SiliconFlow is a genuinely usable open-source backend** for skill compression in v0.1. It naturally respects the skill sweet spot, preserves structural load-bearing content, and produces output that would plausibly work as a replacement skill at runtime.

2. **denser's methodology transfers across languages**. The taxonomy's preserve/strip categories (Layer 2 moves) apply identically to Chinese input. The compression rationale bullets produced by GLM itself list the same move categories as the self-compression case: strip motivational preamble, condense enumerations, remove reference materials, etc.

3. **The 61–101s latency of GLM-4.6 is the real cost**. At this speed, interactive-use denser via GLM-4.6 is viable for rare "compress when written" flows but not for high-frequency batch use. Claude Opus 4.6 at ~20s is better for production; GLM-4.6 is better for "I don't have an Anthropic API key".

4. **Unexpected behaviors happen at cross-model boundaries**. Denser v0.1's prompts are tuned on Claude; when applied to other models, interactions emerge (like the English translation observed here). This is direct empirical evidence for the v0.3 workstream on per-model prompt variants.

---

## Reproducing this compression

```bash
# Ensure SILICONFLOW_API_KEY is set in .env or env
python -c "
from denser import compress
from denser.backends import SiliconFlowBackend
from pathlib import Path

text = Path('~/.claude/skills/luming/SKILL.md').expanduser().read_text(encoding='utf-8')
result = compress(text, task_type='skill', backend=SiliconFlowBackend(model='zai-org/GLM-4.6'))
print(result.compressed)
print(f'Density: {result.actual_density:.3f} (target 0.375, sweet spot 0.30-0.45)')
"
```

Expected: density in 0.42 – 0.44 range (some model-day variance), output in English or mixed Chinese-English.

---

## Files in this directory

- `verbose.md` — the original skill (user's `~/.claude/skills/luming/SKILL.md`, Apr 2026)
- `dense.md` — GLM-4.6 compressed output, used as-is
- `rationale_raw.md` — GLM-4.6's self-reported compression rationale (raw, unedited)
- `notes.md` — this file, methodology application

Note: `verbose.md` is shared with permission as a real-world example. Its content (Lu Ming's publicly-discussed academic frameworks) contains no private user information.
