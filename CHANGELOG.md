# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (v0.2 pre-release)
- **Claude Code skill `denser-compress`** — runs inside Claude Code's authenticated
  session, no API key needed. Installs to `~/.claude/skills/denser-compress/`
  via `denser/skills/install.sh` (bash) or `install.ps1` (PowerShell). Ships
  with `SKILL.md` (trigger rules + workflow) and `REFERENCE_taxonomy.md`
  (auto-generated from `denser.taxonomy` via `scripts/sync_skill_reference.py`).
- CI sync test ensures the skill's reference file stays in lockstep with the
  Python taxonomy.

- **`docs/METHODOLOGY.md`** — 4-layer compression methodology extracted from
  real compression sessions. Framing questions → macro moves → micro tactics →
  stopping rules, grounded in Shannon, Grice, RLHF reliability, and attention
  mechanics. Gives contributors and practitioners a reusable mental model
  rather than ad-hoc rules.
- **Self-compression case study** — `examples/skills/02_denser_compress_self/`
  shows denser's own Claude Code skill compressing itself using the methodology:
  1249 → 526 tokens (-58%, density 0.42, inside the `skill` sweet spot). Full
  section-by-section walkthrough in `notes.md`, featured on the README landing.

- **`OpenAICompatibleBackend` + `SiliconFlowBackend`** — denser now supports any
  OpenAI-compatible API: OpenAI, SiliconFlow, OpenRouter, Groq, Together, vLLM,
  Ollama, and others. `SiliconFlowBackend` ships preconfigured for 中国友好
  access to GLM, DeepSeek, Qwen, Kimi, and StepFun models.
- **`python-dotenv` support** — denser now auto-loads `.env` from the cwd on
  import, so `SILICONFLOW_API_KEY` etc. can be kept in a file instead of
  shell environment (safer: `.env` is gitignored and never enters shell
  history).
- **CLI `--backend`** flag: choose `claude` (default), `siliconflow`, or
  `openai-compat` (with `--base-url` + `--model`).
- **`docs/CROSS_MODEL_NOTES.md`** — empirical benchmark of 12 models on the
  self-compression task. Finding: only Claude Opus 4.6 and GLM-4.6 naturally
  land in the `skill` sweet spot (0.30-0.45) with the default prompt;
  newer/larger models trend conservative; older/smaller models over-compress;
  reasoning models add latency without accuracy benefit.
- **README**: backend-choice guidance and "why not reasoning models" rationale
  derived from the cross-model data.

- **Pre-commit hook** (`integrations/pre-commit-hook.sh` + `.ps1`) — blocks
  commits of LLM-input files that exceed their task type's sweet-spot token
  ceiling by ≥10%. Fast (local estimator, no API call), bypassable
  (`SKIP_DENSER=1`). Infers task type from path. See `integrations/README.md`.
- **`denser.precommit` module** — the hook's Python implementation, also
  invokable directly: `python -m denser.precommit <files...>`.
- **Second case study** — `examples/skills/03_luming_glm46/` — a real
  Chinese-language Claude Code skill (`~/.claude/skills/luming/SKILL.md`,
  1432 tokens) compressed with GLM-4.6 via SiliconFlow to 627 tokens
  (density 0.438, inside sweet spot, 56% savings). Validates the v0.1
  backend recommendation on a real-world non-self-authored skill, and
  surfaces one unexpected behavior (GLM translates Chinese instructions
  to English during compression) worth a v0.3 `preserve_language` flag.

### Planned for v0.2 (remaining)
- Web playground
- Language-specific compression tuning (preserve_language flag)
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
