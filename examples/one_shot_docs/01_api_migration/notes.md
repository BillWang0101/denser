# Notes: API migration one-shot doc compression

**Original**: 590 words (~770 tokens)
**Compressed**: 195 words (~260 tokens)
**Density**: 0.34 (66% savings)
**Task-type sweet spot for `one_shot_doc`**: 0.40 – 0.60

Slightly below typical sweet spot because the original is narrative-heavy — about 30% of the original is context-setting rather than actionable instructions.

## Preserved

- **Goal** (one line)
- **Endpoint mapping** table — unambiguous, load-bearing
- **Numbered steps** — actionable procedure
- **Hard constraints** as `MUST` / `Do NOT` rules with reasons
- **Acceptance criteria** — how the LLM knows the task is done
- **Decision criteria** — how to handle ambiguity (the escape hatch is load-bearing)

## Stripped

- "Hi Claude!" greeting and narrative preamble
- **"Why this matters"** section — business rationale; doesn't change the LLM's execution
- **"Background"** — history of the v1 API's growth
- **"Future work"** — 47 more files to go; irrelevant to this specific task
- "Good luck" closing
- Expansive explanations of each auth change — consolidated into Hard constraints

## Risk check

- The restructuring into `# Hard constraints` is deliberately explicit with `MUST` / `NEVER` — these three rules are exactly the kind of thing compression typically strips. Calling them out in their own section reduces the risk.
- **Acceptance criteria** preserved completely — task completion is unambiguous.
- **Safety preservation**: no explicit safety rules in either version; the "don't invent new storage" rule was preserved for operational correctness (not security, but worth keeping).
