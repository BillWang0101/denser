# Notes: monorepo CLAUDE.md compression

**Original**: 438 words (~570 tokens)
**Compressed**: 175 words (~230 tokens)
**Density**: 0.40 (60% savings)
**Task-type sweet spot for `claude_md`**: 0.35 – 0.50

Right in the middle of the sweet spot — CLAUDE.md files benefit from aggressive compression because much of their content is auto-discoverable from the repo.

## Preserved

- **All coding conventions** — non-obvious rules the LLM cannot infer
- **"Things the Team Has Learned"** section restructured as "Hidden constraints" — these are the highest-value entries in the whole file because they encode specific incidents
- **Git conventions** — project policy, non-inferable
- **Tooling choices** — inference-resistant (Bun vs npm, Vitest vs Jest)

## Stripped

- **Welcome message** and project overview — LLM reads code, doesn't need narrative
- **Directory structure enumeration** — available via `ls` in seconds
- **"Running the Project"** steps — already in README.md
- **Build/test commands table** — in `package.json` scripts
- **"Questions or Issues?"** social section — not operational
- **Description of tech stack** — visible in `package.json`

## Risk check

- The "deploy via Vercel" mention was preserved (inside "Hidden constraints") because the env-var placement matters for debugging, which the LLM can't discover from code alone.
- **Safety preservation**: no explicit safety rules; no action required.
- Restructuring around "# Conventions" / "# Hidden constraints" / "# Git" / "# Tooling" provides navigational scaffolding even in the compressed form.
