# denser development runner

Runs the small bundled example corpus for development. This is not yet a
publishable behavior benchmark: the default fixtures are structural checks and
the corpus has eight worked examples.

## Paired Codex capability-profile audit

The repository's strongest end-to-end token claim is reproduced by running the
same frozen behavior cases under Codex CLI `standard` and `text-only` profiles.
Calls are submitted in a seeded randomized order, with three trials per case by
default. The script refuses to overwrite an existing report.

```bash
python benchmarks/codex_profile_audit.py \
  --trials 3 --workers 8 --seed 20260817 --respect-system-proxy \
  --output build/codex-profile-audit.json
```

This performs 84 authenticated Codex calls. Use `text-only` only for workloads
that need no files, commands, network, plugins, apps, skills, or memory. The
published run and exact interpretation are documented in
[`docs/CODEX_TEXT_ONLY_CASE_STUDY.md`](../docs/CODEX_TEXT_ONLY_CASE_STUDY.md).

For the preregistered external-project corpus derived from uv's public Codex
rules, use:

```bash
python benchmarks/codex_profile_audit.py \
  --scenario-set uv-public-pilot \
  --trials 3 --workers 8 --seed 20260818 --respect-system-proxy \
  --output build/uv-public-pilot.json
```

## What it does

1. Iterates over all curated example pairs in `examples/`
2. For each pair:
   - Compresses the `verbose.md` using denser + Claude Opus 4.6
   - Evaluates both `verbose.md` (original) and the candidate on built-in structural checks
   - Reports pass-rate delta + token savings
3. Aggregates per-task-type statistics for the README table

## Requirements

- `ANTHROPIC_API_KEY` environment variable set
- `pip install -e ".[dev]"` from repo root

## Run

```bash
python benchmarks/run.py                    # all task types
python benchmarks/run.py --type skill       # one task type
python benchmarks/run.py --n-trials 3       # repeat judge calls (not an equivalence test)
python benchmarks/run.py --out results.json # persist results
```

## Expected wall time

- `--n-trials 1` (CI smoke): ~2-5 minutes for the full corpus
- Higher trial counts multiply runtime but do not create asset-specific behavior coverage

## Cost

Rough API bill per run at default `--n-trials 1`:
- Compression (Opus 4.6): $0.01-0.05 per example
- Evaluation (Haiku 4.5): < $0.001 per example

Per-run total: typically < $1 at v0.1 corpus size.

## How to interpret output

Use the output to debug candidate generation and fixture plumbing. Savings and
built-in pass-rate deltas must not be presented as average behavior results.
The most valuable additions are realistic positive, negative, exceptional, and
adversarial cases for a specific asset, together with provenance and raw output.

## Contributing benchmark results

If you run this on your own examples, we welcome PRs adding them to `examples/`. See `docs/CONTRIBUTING.md` §"Submitting a sample pair".
