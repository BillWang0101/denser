# Holdout authoring record

The candidate was frozen first in Git commit
`2f88ee52a9bdc68f6c215b8eae96d74f247c9af8`. The authoring call then received
only `AGENTS.md`, `preservation-contract.json`, and the instruction below. It
did not receive `AGENTS.dense.md` or any description of its wording.

The call used independent Codex CLI 0.147.0, `gpt-5.6-sol`, medium reasoning,
an ephemeral read-only session, ignored user configuration, and disabled apps,
memories, and multi-agent features. The model was explicitly told not to inspect
the filesystem or use tools. The completed call reported 21,694 input tokens,
9,984 cached input tokens, 2,434 output tokens, 402 reasoning-output tokens, no
transport fallback, and no operational error.

## Authoring instruction

```text
You are an independent blind evaluation author for LLM project instructions.
The candidate instruction is deliberately not provided. Do not inspect the filesystem, run tools,
or infer any candidate wording. Use only the upstream instruction and preservation contract in the
user message. Create realistic holdout workload cases that test behavior, not text similarity.
Prefer exact deterministic outputs. Prompts must not reveal their expected answer. Cover positive,
near-miss, failure, permission, and adversarial boundaries where supported by the source. Do not
invent obligations absent from the source. Return one JSON object only, with a top-level tasks array;
each task uses task_type claude_md, a unique name, description, pass_threshold 1.0, max_tokens at
most 96, covers contract IDs, and cases using denser replay fields name, category, prompt, expected,
optional match_mode, and optional forbidden. Cover every C001-C015 at least once. Include at least
10 cases total. Make one case a strong negative-control target for a critical permission boundary.
```

The generated draft contained 23 cases. Review normalized only the category
labels to denser's existing enum values, removed redundant explicit
`match_mode: exact` fields, and shortened task descriptions. It did not change
prompts, expected outputs, coverage IDs, or the frozen candidate.

This procedure establishes chronological blindness for this candidate. Once
published, the cases are visible and therefore become development tests for
future candidates; a future public comparison needs a newly authored holdout.

Post-run audit found that `scheduled_ci_role` had an incorrect exact expected
string and excluded it from the behavior claim without changing the raw report.
See [`blind-audit.2026-08-17.json`](blind-audit.2026-08-17.json).
