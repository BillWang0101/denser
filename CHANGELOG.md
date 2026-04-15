# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for v0.2
- Claude Code skill integration (compress skills in place)
- Pre-commit hook
- Web playground
- Language-specific compression tuning (Chinese, beyond English)
- Cross-model transfer benchmarks

## [0.1.0] — 2026-04-15

### Added

**Core framework**
- Task type taxonomy: `skill`, `system_prompt`, `tool_description`, `memory_entry`, `claude_md`, `one_shot_doc`
- `compress(text, task_type=..., target_density=...)` — LLM-guided task-typed compression
- `evaluate(text, task_type=...)` — golden-task pass-rate evaluation
- `compare(original, compressed, task_type=...)` — side-by-side pass-rate delta
- `curve(text, task_type=...)` — Signal Density Curve sweep + peak fit
- Claude Opus 4.6 backend with ephemeral prompt caching on system prompts

**CLI**
- `denser compress` — compress a file
- `denser eval` — evaluate against golden tasks (optional `--compare-to`)
- `denser curve` — plot the signal density curve (optional PNG output)
- `denser info` — offline taxonomy reference

**Fixtures**
- 12 built-in golden tasks, at least one per task type
- 6 curated before/after sample pairs under `examples/`

**Documentation**
- `README.md` — public-facing overview and quickstart
- `docs/WHITEPAPER.md` — formal methodology and Signal Density Curve framework
- `docs/TAXONOMY.md` — operational reference for each task type
- `docs/COOKBOOK.md` — 10 concrete usage recipes
- `docs/CONTRIBUTING.md` — contribution guidelines
- `PROJECT_PLAN.md` — internal roadmap (public for transparency)

**Benchmarks**
- `benchmarks/run.py` — reproducible benchmark runner across all example pairs

**Infrastructure**
- 60 unit tests covering taxonomy, compress pipeline, eval harness, density curve math
- Gated integration tests for live API validation
- GitHub Actions CI with Python 3.10 – 3.13 matrix
- Apache 2.0 license
