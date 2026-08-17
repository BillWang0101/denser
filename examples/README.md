# denser examples

> These are worked rewrite examples, not an independent benchmark. Token counts
> use local estimates unless stated otherwise, density ranges are exploratory,
> and preserve-list review is structural rather than proof of behavior
> preservation. Contributions should add realistic behavior cases and
> provenance alongside future examples.

Curated before/after pairs documenting possible rewrites for each task type.

Most subdirectories contain:
- `verbose.md` — the original, typical "as-written" text
- `dense.md` — the compressed equivalent, hand-curated as a golden reference
- `notes.md` — what was removed and why (feeds into the benchmark suite)

These pairs serve three purposes:

1. **Documentation**: concrete evidence that denser produces non-trivial compression
2. **Behavior-test inputs**: asset-specific suites can replay original and candidate
3. **Contribution templates**: PRs adding more pairs follow this structure

## Structure

```
examples/
  skills/
    01_pr_review/
      verbose.md
      dense.md
      notes.md
    02_commit_message/
      verbose.md
      dense.md
      notes.md
  system_prompts/
    ...
  tool_descriptions/
    ...
  memory_entries/
    ...
  claude_md/
    ...
  one_shot_docs/
    ...
  project_instructions/
    01_codex_release_ops/
      AGENTS.md
      AGENTS.dense.md
      replay.json
      README.md
    02_openai_python_version_policy/
      AGENTS.md
      AGENTS.dense.md
      preservation-contract.json
      replay.holdout.json
      holdout-authoring.md
      README.md
```

## Contributing a new pair

1. Pick a task type directory (or create one)
2. Copy an existing pair's structure
3. Write `verbose.md` with a realistic-but-uncompressed version
4. Either hand-compress or run `denser compress` to produce `dense.md`
5. Write `notes.md` describing what was preserved vs. stripped, and why
6. Open a PR

Pairs with instructive behavior differences, failed candidates, negative cases,
and surprising preservation decisions are especially welcome. The
`project_instructions` cases show the preferred provenance and replay-suite
shape. New blind evidence should freeze the candidate before a separate process
authors the holdout and should bind both asset hashes in suite metadata.
