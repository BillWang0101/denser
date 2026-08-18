# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0-alpha.2] — 2026-08-18

### Added
- Added a preregistered public-project transfer check derived from frozen Astral
  uv issue-triage and workflow-failure prompts. Across 84 authenticated Codex
  calls, both profiles produced all expected decisions while `text-only/v1`
  reduced provider-reported input per call by 10.50% and 10.74%, with no
  operational errors or transport fallbacks.

## [0.2.0-alpha.1] — 2026-08-18

### Added — context behavior audit
- Added `denser audit` and the `audit_context` Python interface for comparing a
  baseline with any rewritten, selectively loaded, or externally compacted
  textual context snapshot.
- A positive verdict now requires exact covered-case parity plus a detected
  regression in a caller-supplied known-bad negative control. Equal scores
  without a sensitive control are reported as inconclusive.
- Audit reports separate local asset-length estimates from provider-reported
  full input usage, so file compression is not presented as end-to-end savings.
- Added an explicit Codex CLI `text-only` capability profile for pre-bundled
  tasks that need no tools, files, network, plugins, apps, skills, or memory.
  A seeded, randomized, three-trial audit completed all 84 paired-profile calls
  without operational errors or transport fallbacks. Both profiles passed all
  covered cases while `text-only` reduced provider-reported input per call by
  10.55% and 10.60% across the two workloads.
- Added a reproducible capability-profile benchmark and a public per-call
  evidence report. An initial strict run exposed one missing output-contract
  behavior; `text-only/v1` fixes that boundary and the full audit was rerun.

### Changed — behavior-fidelity pivot
- Repositioned denser from a compression-first tool to an evidence layer for
  context changes. Existing compression and density commands remain available
  as experimental candidate-generation tools.

### Added — deterministic behavior replay
- Added `denser replay` and a Python replay API that run instruction assets as
  system instructions against explicit workload prompts.
- Added exact, contains, and regular-expression output matchers, paired
  reproducibly randomized original/candidate calls, and separate operational
  error accounting.
- Integrated replay-task evidence with preservation-contract verification.
- Added a redistributable Codex-style `AGENTS.md` release-operations pilot with
  positive, near-miss, failure, permission, and adversarial cases.
- Added a replay-only backend for an independently installed, authenticated
  Codex CLI. It runs ephemeral read-only turns and records sanitized status,
  latency, transport-fallback, and token-usage evidence in replay report `v2`.
- Added an allowlisted, non-sensitive runtime-configuration snapshot to single
  and comparison replay reports, upgrading the report schema to `v3`. Existing
  backends without the optional property remain compatible.
- Added replay suite `v2` holdout metadata with normalized source/candidate
  hashes, a candidate-freeze commit, and a non-sensitive authoring record.
  Replay report `v4` preserves that evidence and blocks changed frozen assets
  before backend execution.
- Added an Apache-2.0 `openai-python` `AGENTS.md` case whose candidate was frozen
  before an independent Codex CLI process authored a 23-case holdout suite.
  Post-run audit retained 22 valid cases, excluded one incorrect exact matcher,
  and recorded both successful and failed negative-control designs.
- Added per-call replay progress with completed/total counts, asset side, case,
  and trial; CLI progress can be disabled with `--no-progress`.
- Added a candidate-frozen, source-only permission-causal holdout plus an
  independently reviewed neutral counterfactual. The source and candidate each
  passed 15/15; four of five counterfactual cases fully flipped, while one
  bounded issue-refresh case remained unstable and is reported as a limitation.

### Changed — credibility reset
- Reframed denser around evidence-guided instruction refactoring and added
  `docs/DESIGN.md` as the active product/evidence plan.
- Labeled built-in eval fixtures as structural checks rather than proof of
  behavior preservation.
- Reclassified density ranges and the quadratic curve as exploratory.
- Removed uncommitted benchmark numbers and general backend rankings from the
  README.
- Made the pre-commit integration advisory; file length alone no longer blocks
  a commit.
- Updated repository links from `BillWang0101/denser` to `Evostructs/denser`.

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
  1249 → 526 estimated tokens (-58%, density 0.42, inside the exploratory
  `skill` generation range). This is a hand-reviewed structural example, not an
  asset-specific behavior result.

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
- **`docs/CROSS_MODEL_NOTES.md`** — single-input exploratory observations from
  12 model runs on the self-compression task. Length and latency varied, but the
  run did not establish behavior preservation or a general model ranking.
- **README**: backend-choice guidance now requires validation on the model and
  workload that will execute the instruction.

- **Pre-commit hook** (`integrations/pre-commit-hook.sh` + `.ps1`) — prints an
  advisory review suggestion for recognized LLM-input files above a heuristic
  reference size. It uses a local estimate, makes no API call, and never blocks
  a commit because of length alone.
- **`denser.precommit` module** — the hook's Python implementation, also
  invokable directly: `python -m denser.precommit <files...>`.
- **Second case study** — `examples/skills/03_luming_glm46/` — a real
  Chinese-language Claude Code skill (`~/.claude/skills/luming/SKILL.md`,
  1432 tokens) compressed with GLM-4.6 via SiliconFlow to 627 tokens
  (density 0.438, inside the exploratory range, 56% estimated savings). This
  second observation does not validate a general backend recommendation or a
  runtime-safe replacement; it also records an unexpected language change.

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
