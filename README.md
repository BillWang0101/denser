# denser

> Refactor LLM instructions into shorter candidates, then verify what they still do.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/Evostructs/denser/actions/workflows/ci.yml/badge.svg)](https://github.com/Evostructs/denser/actions/workflows/ci.yml)
![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)

![Experimental density sweep across instruction roles](docs/assets/hero.png)

> [!IMPORTANT]
> denser is an alpha research prototype. The current built-in fixtures perform
> structural checks; they do not prove behavior preservation for an arbitrary
> instruction asset. Asset-specific deterministic behavior replay is available,
> but its evidence applies only to the exact workload and execution model used.
> See [`docs/DESIGN.md`](docs/DESIGN.md) for the evidence standard and the active
> implementation plan.

---

## 🔁 Featured: denser-compress compresses itself

denser ships with a Claude Code skill called `denser-compress`. As the first public demo, we compressed that skill's own `SKILL.md` using the denser methodology.

| | Estimated tokens | Density | Exploratory range |
|---|---:|---:|---:|
| Case-study source snapshot (`verbose.md`) | **1249** | 1.00 | — |
| Case-study candidate snapshot (`dense.md`) | **526** | **0.42** | 0.30 – 0.45 ✓ |

**This hand-reviewed demo is 58% shorter by denser's local estimator.** It
preserves the categories in the current checklist, but it has not yet been
validated by an asset-specific behavior suite.

Read the full walkthrough — what was cut, what survived, and why — in [`examples/skills/02_denser_compress_self/notes.md`](examples/skills/02_denser_compress_self/notes.md). The methodology applied is documented in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

The example demonstrates the rewrite workflow; it is not a general performance
claim.

---

## The Problem

In the agent era, the same text gets loaded into an LLM **every turn**:

- Skills reloaded on each relevant request
- System prompts prefixed to every call
- Tool descriptions parsed thousands of times per session
- Memory entries competing for a finite context budget

Verbose instructions cost tokens and can make important rules harder to locate.
Whether shortening helps depends on the asset, workload, execution model, and
prompt-cache behavior.

Existing work already covers token pruning, structured prompt optimization,
prompt evaluation, and runtime context management. denser takes a narrower
path: version-controlled instruction assets, role-aware rewrite guidance, and a
reviewable path toward behavior regression testing.

---

## What denser does

```bash
denser inspect --type skill my_skill.md
denser optimize --type skill my_skill.md \
  --out my_skill.optimized.md \
  --evidence-out my_skill.evidence.json
denser compress --type skill my_skill.md
denser verify --type skill my_skill.md my_skill.dense.md
denser replay --type claude_md AGENTS.md --suite replay.json \
  --compare-to AGENTS.dense.md --backend codex-cli \
  --model gpt-5.6-sol --codex-reasoning-effort medium
```

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  my_skill.md  →  my_skill.dense.md
  182 tokens   →  61 tokens   (-66%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

`inspect` first performs an offline scan and produces a source-linked
preservation contract: triggers, exclusions, hard constraints, safety and
permission rules, output obligations, failure paths, and protected literals.
It makes no model or network calls. `optimize` gives the contract to the
generator, samples multiple candidates, verifies each one, and recommends the
shortest passing option; the original always remains a candidate. It never
overwrites the source or an existing output file. `verify` rejects missing
metadata and protected literals, and leaves changed obligations at `review`
until they have deterministic or explicitly mapped behavior evidence.
`replay` executes realistic requests with the instruction asset in the backend's
system-instruction position, scores outputs with deterministic rules, and
randomizes paired original/candidate call order. The CLI reports each completed
call with total progress, asset side, case, and trial; use `--no-progress` for
quiet runs. `compress` and `eval` remain
lower-level experimental entry points. A candidate should not replace its
source until it passes an asset-specific behavior suite.

---

## Three differentiators

### 1. Role-aware rewriting

Different instruction assets have different failure modes. denser currently
ships six rewrite profiles. Their density ranges are exploratory generation
defaults, not measured optima:

| Task type | What to preserve | What to strip | Exploratory target |
|---|---|---|---|
| `skill` | trigger rules, hard constraints, 1-2 canonical examples | meta-commentary, redundant examples, hedging | 0.30 – 0.45 of original |
| `system_prompt` | role, capabilities, output format contracts | motivational preamble, redundant do-s and don't-s | 0.40 – 0.55 |
| `tool_description` | when-to-use, exact inputs, failure modes | prose explanation of parameters (already in schema) | 0.45 – 0.60 |
| `memory_entry` | the fact + the "why" (triggers judgment) | example scenarios, timestamps | 0.58 – 0.78 |
| `claude_md` | project conventions, non-obvious invariants | API docs, auto-discoverable structure | 0.35 – 0.50 |
| `one_shot_doc` | the actionable instruction | background context that's implicit | 0.40 – 0.60 |

### 2. Structural checks and behavior tasks

Compare an original and candidate with a deterministic suite written for that
asset:

```bash
denser replay --type claude_md AGENTS.md --suite replay.json \
  --compare-to AGENTS.dense.md --backend codex-cli \
  --model gpt-5.6-sol --codex-reasoning-effort medium \
  --n-trials 3 --seed 20260817
```

- Built-in fixtures check for structural signals such as an explicit trigger or
  hard constraint.
- Replay suites exercise real triggers, near misses, permission boundaries,
  failure paths, and adversarial requests against the execution backend.
- Outputs are checked with exact, contains, or regular-expression rules; model
  and service errors remain separate from content failures.
- The Codex CLI adapter uses an independent authenticated CLI, an ephemeral
  read-only turn, and records sanitized per-call status, latency, and token
  usage without copying local authentication or raw diagnostics into reports.
- Replay report `v3` introduced a sanitized top-level runtime configuration:
  backend kind, model, Codex CLI version, reasoning effort, timeout, isolation
  flags, system-proxy choice, and disabled features. Executable paths, account
  details, credentials, thread identifiers, and raw diagnostics are excluded.
- Holdout suite `v2` binds the source and candidate hashes to a candidate-freeze
  commit. Replay report `v4` carries that freeze and the non-sensitive authoring
  record, and refuses changed assets before making a model call.
- Reports show observed pass rates. They do not yet compute a
  confidence interval or automatically establish behavioral equivalence.

See the synthetic redistributable
[`AGENTS.md` release-operations case](examples/project_instructions/01_codex_release_ops/README.md)
and the licensed upstream
[`openai-python` policy case](examples/project_instructions/02_openai_python_version_policy/README.md)
for complete sources, candidates, five-category workloads, provenance, and
reproduction commands. The second case freezes its candidate before an
independent process authors the holdout.

Replay JSON contains raw model outputs. Store it with the same access controls
as the instruction asset and workload prompts.

### 3. Experimental density sweep

`denser curve` samples candidates at several target densities and plots the
observed scores. The relationship is not assumed to be concave: it may be
monotone, flat, noisy, multi-peaked, or favor the original.

```
task pass-rate
    ▲
1.0 ┤      ╭────╮
    │    ╭─╯    ╰─╮
    │   ╱         ╲
    │  ╱           ╲
0.5 ┤ ╱             ╲
    │╱               ╲___
    └────────────────────────▶
    1.0  0.6  0.4  0.2  0.0
          compression ratio
          (smaller = denser)
```

The current implementation also draws an optional quadratic fit. Treat it as a
visual aid, not proof of an optimum.

```bash
denser curve --type skill my_skill.md --out curve.png
```

See [`docs/DESIGN.md`](docs/DESIGN.md) for the active evidence standard and
[`docs/WHITEPAPER.md`](docs/WHITEPAPER.md) for the original research hypothesis.

---

## Why static instruction assets

Skills, system/developer instructions, tool descriptions, project rules, and
memory policies are reused and often version controlled. That makes them
reviewable and testable in a way that transient chat history is not. Prompt
caching and runtime compaction can reduce some operational costs, but they do
not show whether a changed instruction still triggers and behaves correctly.

---

## Installation

### Option 1 — As a Claude Code skill (no API key, no Python)

If you use Claude Code, install the `denser-compress` skill:

```bash
git clone https://github.com/Evostructs/denser.git
bash denser/denser/skills/install.sh        # macOS / Linux
# or: denser\denser\skills\install.ps1       # Windows PowerShell
```

Restart Claude Code. Then in any session:

> "compress this skill at `~/.claude/skills/my-skill/SKILL.md`"

The skill runs inside Claude Code's authenticated session — no separate API key needed. See [`denser/skills/README.md`](denser/skills/README.md).

### Option 2 — As a Python library from source

```bash
git clone https://github.com/Evostructs/denser.git
cd denser
pip install -e ".[dev]"
```

---

## Quickstart

### Inspect and verify offline

```python
from denser import inspect, verify
from pathlib import Path

original = Path("my_skill.md").read_text(encoding="utf-8")
candidate = Path("my_skill.dense.md").read_text(encoding="utf-8")

contract = inspect(original, task_type="skill")
report = verify(
    original,
    candidate,
    task_type="skill",
    inspection=contract,
)

print(report.decision.value)
print(report.missing_literals)
```

The offline verifier exits `0` for `pass`, `3` for `review`, and `2` for
`reject`. A changed semantic obligation remains at `review` unless it is
retained verbatim or covered by an explicitly mapped behavior task. Custom
`GoldenTask` objects map evidence with `covers=("C003", ...)`; service errors
are reported separately and never count as successful behavior evidence.

For deterministic execution rather than judge-based scoring, load a replay
suite and pass it to `verify` with the same backend that will execute the asset:

```python
from denser import load_replay_tasks, verify

suite = load_replay_tasks("replay.json")
report = verify(
    original,
    candidate,
    task_type="claude_md",
    replay_tasks=suite,
    execution_backend=my_backend,
    replay_seed=20260817,
)
```

### Optimize with multiple candidates

```python
from denser import optimize

report = optimize(
    original,
    task_type="skill",
    target_densities=(0.30, 0.40, 0.50),
    source_name="my_skill.md",
)

print(report.recommended_candidate_id)
print(report.recommendation_reason)
print(report.recommended.text)
```

The returned report uses the versioned
`denser.optimization-report/v1` schema and records source hash, candidates,
contract coverage, model identifiers, logical model calls, operational errors,
token-counting method, and timing. The default counter is the explicitly
approximate offline `heuristic-v1`. For provider-aware Anthropic counts, pass
`token_counter=AnthropicTokenCounter(model="...")`; it raises on failure rather
than silently substituting an estimate. CLI evidence JSON includes source and
candidate text; keep it with the same access controls as the instruction asset.
Without mapped behavior tasks, semantic rewrites remain at `review`, so a
conservative run may correctly recommend the original.

### Compress a skill

```python
from denser import compress

with open("my_skill.md") as f:
    result = compress(f.read(), task_type="skill")

print(result.compressed)
print(f"Saved {result.savings_pct:.0%} tokens")
print(f"Rationale:\n{result.rationale}")
```

### Evaluate a compression

```python
from denser import compare, compress
from pathlib import Path

text = Path("my_skill.md").read_text(encoding="utf-8")
result = compress(text, task_type="skill")

report = compare(
    original=text,
    compressed=result.compressed,
    task_type="skill",
    n_trials=3,
)

print(
    f"Observed structural-check pass rate: "
    f"{report.original.overall_pass_rate:.2%} → "
    f"{report.compressed.overall_pass_rate:.2%}"
)
```

### Plot the density curve

```python
from denser import curve

c = curve(text, task_type="skill", densities=(0.3, 0.5, 0.7, 1.0))
c.plot(out="curve.png")
print(f"Best observed/fitted density: {c.peak_density:.2f}")
```

---

## Supported backends

denser ships three generation backends and one replay-only local CLI adapter:

```python
from denser.backends import (
    ClaudeBackend,
    CodexCliBackend,
    OpenAICompatibleBackend,
    SiliconFlowBackend,
)

# Anthropic adapter used by the current default
ClaudeBackend(model="claude-opus-4-6")

# SiliconFlow preset for its OpenAI-compatible endpoint
SiliconFlowBackend(model="zai-org/GLM-4.6")

# Generic Chat Completions-compatible endpoint
OpenAICompatibleBackend(base_url="https://api.openai.com/v1", model="gpt-4o")

# Authenticated local Codex CLI; available to `denser replay` only
CodexCliBackend(model="gpt-5.6-sol", reasoning_effort="medium")
```

On Windows, install the official `@openai/codex` package independently. The
adapter discovers `%APPDATA%\\npm\\codex.cmd`, accepts `DENSER_CODEX_CLI` or
`--codex-cli-path`, and deliberately rejects the desktop app's private
WindowsApps executable.

### Which backend to use

Backend quality is asset- and workload-dependent. The observations in
[`docs/CROSS_MODEL_NOTES.md`](docs/CROSS_MODEL_NOTES.md) come from one source
asset with one generation per model plus a separate repeated behavior-replay
follow-up on two project-instruction cases. They are useful for reproducing
prompt-following differences, but they do not support general model rankings.
Validate the candidate on the model that will execute the instruction.

For replay providers whose reasoning tokens share the output allowance, use
`--openai-thinking-mode disabled` for short exact-label tasks when the provider
supports the compatible `thinking` field. The default remains
`provider-default`; denser does not silently change provider behavior.

---

## Benchmarks

No general performance benchmark is published yet. The repository currently
contains ten before/after examples, including two `AGENTS.md` cases. The second
uses a candidate-frozen, chronologically blind holdout, but the public examples
as a whole are not an independent evaluation dataset.

The runner in [`benchmarks/`](benchmarks/) can execute the current corpus with a
live backend. Results are publishable only when raw output, model/settings,
asset-specific behavior tasks, provenance, and a reproduction command are
committed together.

---

## Integrations

### Pre-commit hook

Add an advisory size review for LLM-input files (skills, `CLAUDE.md`, system
prompts, memory entries) with a single copy:

```bash
cp integrations/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook uses a local estimate, makes no API call, and never blocks a commit on
length alone. The reference sizes are review prompts, not quality thresholds.
See [`integrations/README.md`](integrations/README.md).

### Claude Code skill

```bash
bash denser/skills/install.sh
```

The `denser-compress` skill runs inside Claude Code's authenticated session — no separate API key. See [`denser/skills/README.md`](denser/skills/README.md).

---

## Roadmap

- **Phase 0** — align claims, terminology, integrations, and metadata with the committed evidence
- **Phase 1** — preservation contract, source mapping, multi-candidate optimization, and evidence report
- **Phase 2** — deterministic replay and one candidate-frozen holdout are available; broader external workloads remain
- **Phase 3** — external pilot projects, reproducible releases, and evaluation adapters
- **Phase 4** — synthetic and licensed `AGENTS.md` pilots are committed; nested Codex discovery and a current OpenAI-native adapter remain

See [`docs/DESIGN.md`](docs/DESIGN.md) for scope, evidence rules, and delivery
gates. [`PROJECT_PLAN.md`](PROJECT_PLAN.md) is retained as the historical launch
plan.

---

## Contributing

Contributions welcome. See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

Particularly useful:

- Submit a realistic instruction asset with provenance and redistribution terms
- Add positive, negative, exceptional, or adversarial behavior cases
- Report a candidate that passed a structural check but failed in real use
- Reproduce an observation with committed model settings and raw results

---

## Acknowledgements

- **Bill Wang ([@Evostructs](https://github.com/Evostructs))** — project creator
  and maintainer.
- [OpenAI Codex](https://openai.com/codex/) — development and validation support
  for this release.
- [Claude](https://claude.com/product/overview) — development support for
  earlier releases.

---

## Citation

If you use `denser` in research or writing, please cite:

```bibtex
@software{wang2026denser,
  author = {Wang, Bill},
  title = {denser: Evidence-Guided Refactoring for LLM Instructions},
  year = {2026},
  url = {https://github.com/Evostructs/denser}
}
```

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE). Redistributed upstream material and
modification notices are listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

*denser is an independent open-source project and is not affiliated with
Anthropic or OpenAI.*
