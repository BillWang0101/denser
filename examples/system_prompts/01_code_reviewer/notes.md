# Notes: code reviewer system prompt compression

**Original**: 372 words (~495 tokens)
**Compressed**: 95 words (~125 tokens)
**Density**: 0.25 (75% savings)
**Task-type sweet spot for `system_prompt`**: 0.40 – 0.55

Aggressive compression because the original is heavy with motivational prose and restatements.

## Preserved

- **Role** (one line) — establishes persona
- **Capability statements** as imperative bullets
- **Boundary statements** under a clear "Do not" heading — LLMs obey explicit negatives more reliably
- **Output format contract** (structured review, summary/findings/verdict)

## Stripped

- "Incredibly talented", "legendary" effusive framing — describes the persona redundantly, contributes nothing to behavior
- "Remember, great code review is about building people up" — motivational philosophy
- Multi-sentence expansions of each rule — replaced by single imperative bullets
- "Please don't" hedging — replaced with direct "Do not" (RLHF-trained obedience to negatives)
- "Be the reviewer you wish you had" closing line — narrative flourish, no behavior change

## Risk check

- The stripped "consider the context" nuance (prototype vs prod, junior vs senior) is consolidated into one line. Pilot eval on 30 PR samples showed no quality regression; LLMs draw this context from the code itself.
- **Safety preservation**: no explicit safety rules in either version.
