# Notes: PR Review compression

**Original**: 303 words (~400 tokens)
**Compressed**: 71 words (~95 tokens)
**Density**: 0.24 (76% savings)
**Task-type sweet spot for `skill`**: 0.30 – 0.45

This compression is slightly below the typical sweet spot because the
original is especially wordy — much of it is meta-commentary about the
skill's purpose and philosophy rather than actionable rules. Aggressive
stripping is justified.

## Preserved

- **Trigger condition** (one line) — load-bearing for skill activation
- **The 4-step procedure** — actionable instructions
- **Hard constraints** — kept as explicit `NEVER` rules (LLMs obey `NEVER` more reliably than "please don't")

## Stripped

- `## Purpose` section — meta-commentary about what the skill does. The LLM is already running the skill; it doesn't need to be told what it's doing.
- Multi-bullet expansion of "when to use" — collapsed to one line; specific phrasings of requests are inferable from training.
- `## Example` section — the structure of a good review emerges from following the 4-step procedure; a concrete example adds length without adding information.
- Closing philosophical line — "the goal is to help the author ship good code" — motivational, not operational.
- Hedging language — "please consider", "it's often the case that" — replaced with direct imperatives.

## Risk check

- **Could compression hurt**: the stripped "Example" section might have helped the LLM structure output better. Pilot eval: no measurable pass-rate difference across 30 test reviews.
- **Safety preservation**: no explicit safety rules in either version — nothing safety-critical lost.
