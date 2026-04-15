# Notes: build tool memory entry compression

**Original**: 253 words (~330 tokens)
**Compressed**: 83 words (~110 tokens)
**Density**: 0.33 (67% savings)
**Task-type sweet spot for `memory_entry`**: 0.58 – 0.78

Below typical sweet spot because the original has substantial reminiscence framing ("I recall that a while ago...") that's purely narrative. Memory entries benefit from structure even more than skills.

## Preserved

- **The fact**: use bun, not npm; concrete commands
- **The "why"**: March incident + speed + TypeScript — needed for edge-case judgment (e.g., "what if a script specifically needs npm?")
- **The "when to apply"**: explicit condition for retrieval relevance
- **Non-obvious detail**: CI and Docker also use Bun — prevents the LLM from suggesting a partial-migration workaround

## Stripped

- "Probably Q2 of last year" — temporal guessing, not load-bearing
- The `yarn`/`pnpm` consideration story — only Bun won, the rest is irrelevant
- Expansion on `bun publish`, `bun test` etc. — the one-line "all JS operations" covers it
- "Worth mentioning" narrative connector

## Risk check

- The March incident detail was almost compressed out. Decision: keep the *reason* (lockfile divergence) because it drives what to do if a contributor proposes relaxing the rule.
- **Safety preservation**: no safety rules; no action required.
