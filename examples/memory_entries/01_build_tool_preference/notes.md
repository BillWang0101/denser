# Notes: build tool memory entry compression

**Original**: 253 words (~330 tokens)
**Compressed**: 83 words (~110 tokens)
**Density**: 0.33 (67% savings)
**Exploratory generation range for `memory_entry`**: 0.58 – 0.78

Below the working range because the source has substantial reminiscence framing.
Recall and non-application behavior still require asset-specific tests.

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
