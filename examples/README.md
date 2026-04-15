# denser examples

Curated before/after pairs demonstrating the compression each task type produces.

Each subdirectory contains:
- `verbose.md` — the original, typical "as-written" text
- `dense.md` — the compressed equivalent, hand-curated as a golden reference
- `notes.md` — what was removed and why (feeds into the benchmark suite)

These pairs serve three purposes:

1. **Documentation**: concrete evidence that denser produces non-trivial compression
2. **Golden benchmarks**: the eval harness uses these pairs to measure regression
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
```

## Contributing a new pair

1. Pick a task type directory (or create one)
2. Copy an existing pair's structure
3. Write `verbose.md` with a realistic-but-uncompressed version
4. Either hand-compress or run `denser compress` to produce `dense.md`
5. Write `notes.md` describing what was preserved vs. stripped, and why
6. Open a PR

Pairs with particularly instructive differences (sharp sweet-spot peaks, surprising preservation decisions, cross-type comparisons) are especially welcome.
