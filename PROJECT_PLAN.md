# denser — Internal Shipping Plan

> **Goal**: Ship a flagship-quality open-source project to GitHub within 4 weeks, positioned as *the* tool for finding the signal density sweet spot of LLM inputs across task types.
>
> **Why flagship**: The space of "prompt compression" has low-quality incumbents. A project that ships **task-typed compression + eval-first methodology + a cite-able theoretical framing** will dominate search and social signal. Being first to articulate "Signal Density Curve" as a concept is worth more than 10x the engineering effort of the code itself.

---

## 0. North-star principles

1. **Empirical or bust** — every claim in the README has a reproducible benchmark behind it. No vibes.
2. **Theoretical core first** — the Signal Density Curve framing is the moat. Code is implementation.
3. **Narrow v0.1, zero technical debt** — 6 task types, 1 backend, 1 eval method. Nothing half-done.
4. **Documentation quality = project quality** — for an open-source tool, docs are the product.
5. **Launch with numbers on the box** — no "coming soon". At v0.1, benchmarks are populated.

## 1. Four-week plan

### Week 1 — Foundation (this week)

**Deliverables**
- [x] Repo scaffolding (root files, pyproject, LICENSE)
- [ ] `PROJECT_PLAN.md` (this doc)
- [ ] `docs/WHITEPAPER.md` (full v1 draft — the theoretical contribution)
- [ ] `docs/TAXONOMY.md` (the 6 task types, fully specified)
- [ ] `denser/` Python package skeleton
  - `taxonomy.py` — `TaskType` enum + `TaskSpec` for each type
  - `tokens.py` — token counting (API-based + estimate)
  - `compress.py` — main `compress()` API
  - `backends/base.py` + `backends/claude.py` (with prompt caching)
  - `prompts/skill.py` — the first task-typed compression prompt
  - `prompts/registry.py` — map `TaskType → prompt`
  - `cli.py` — click-based CLI
- [ ] First working end-to-end: `denser compress --type skill input.md` returns compressed text
- [ ] One golden before/after pair in `examples/skills/`
- [ ] CI skeleton (ruff + pytest passing with mock backend)

**Exit gate**: `pip install -e .` works; `denser compress --type skill tests/fixtures/sample.md` produces compressed output using the Claude backend.

### Week 2 — Evaluation + remaining task types

**Deliverables**
- [ ] `eval.py` — task pass-rate harness (LLM-judge + golden assertion matching)
- [ ] Golden-task format defined: `tests/fixtures/golden/skill_trigger.yaml` etc.
- [ ] Prompts for all 6 task types: `skill`, `system_prompt`, `tool_description`, `memory_entry`, `claude_md`, `one_shot_doc`
- [ ] `curve.py` — Signal Density Curve: sweep multiple target densities, measure task pass-rate, fit concave curve, locate peak
- [ ] `denser curve` and `denser eval` CLI commands
- [ ] 10+ benchmark samples per task type (60+ total) collected and formatted
- [ ] Reproducibility: `benchmarks/run.py` reruns all benchmarks from scratch with seed control

**Exit gate**: running `python benchmarks/run.py` from clean state produces the exact numbers in the README benchmarks table.

### Week 3 — Polish + documentation

**Deliverables**
- [ ] `docs/WHITEPAPER.md` finalized with real benchmark data filled in
- [ ] `docs/TAXONOMY.md` finalized
- [ ] `docs/CONTRIBUTING.md`
- [ ] `docs/COOKBOOK.md` — 10+ concrete before/after examples across task types
- [ ] Visual assets:
  - Signal Density Curve hero image (matplotlib, reproducible from `docs/assets/hero.py`)
  - Before/after skill comparison graphic
  - Architecture diagram
- [ ] README final polish (rewrite intro 3x; each under the eye of a "what would a cynical HN commenter say" filter)
- [ ] Test coverage ≥ 85%
- [ ] `ruff check` clean; `mypy --strict` clean
- [ ] PyPI publish dry run (`hatch build` produces valid wheel + sdist)

**Exit gate**: a stranger reading only the README, in under 3 minutes, can correctly describe what denser does, why it exists, and what's different about it.

### Week 4 — Launch

**Deliverables**
- [ ] `BLOG_LAUNCH.md` — 1500-word launch post (technical + narrative)
- [ ] Publish to PyPI (v0.1.0)
- [ ] Push to GitHub public, enable Discussions, enable Sponsors (optional)
- [ ] Submit to awesome-lists (awesome-claude, awesome-prompting, awesome-llm)
- [ ] HN post (Show HN: denser)
- [ ] X/Twitter thread with hero visuals
- [ ] Post to Anthropic Discord / Reddit r/ClaudeAI
- [ ] Post on r/MachineLearning with focus on the WHITEPAPER methodology
- [ ] Email 3-5 influential practitioners with a personalized intro (agent tooling circle)

**Exit gate**: 100 GitHub stars in week 4 is the baseline success metric. 500 stars = strong. 1k+ = viral hit.

---

## 2. Architecture decisions

### 2.1 Language choice

**Python, not TypeScript**, for v0.1. Reasons:
1. ML/research audience is Python-native — more likely to star/fork/cite
2. `anthropic-sdk-python` is more mature than JS equivalent
3. Matplotlib for curve visualization is Python-first
4. PyPI distribution is frictionless

TypeScript port is a v0.3 deliverable if v0.1 traction warrants it.

### 2.2 Compression strategy: LLM-guided, not rule-based

**Decision**: Use Claude itself to do the compression, guided by task-typed system prompts.

**Why not rule-based**:
- Rule-based compression (regex, keyword stripping, syntactic simplification) hits a ceiling fast
- The quality of "what to preserve" is itself an LLM-judgment problem
- LLM-guided compression generalizes across task types we haven't explicitly modeled

**Costs**:
- Per-compression cost: ~$0.01-0.05 in API calls depending on text length
- Slower than rule-based (~2-10s per call)

**Mitigations**:
- Prompt caching on the system prompt (reduces cost ~50% after first call)
- Batch mode for corpus compression
- Clear warning in docs that this is not zero-cost

### 2.3 Prompt caching is mandatory

Every Claude API call goes through `system=[{..., cache_control: {type: 'ephemeral'}}]`. The system prompts for each task type are stable across many compression calls, making cache hits very likely. This is a default-on optimization, not opt-in.

### 2.4 Task pass-rate as the ground truth

**Compression quality** is measured as:

```
pass_rate_compressed - pass_rate_original
```

where `pass_rate` is the fraction of "golden tasks" the LLM passes when given the prompt.

**Golden task format**:

```yaml
# tests/fixtures/golden/skill_test_1.yaml
task_type: skill
prompt_slot: <input>
task_prompt: "When should this skill activate? Respond with yes/no."
test_cases:
  - input: "please review my PR"
    expected: "yes"
  - input: "what is 2+2"
    expected: "no"
pass_threshold: 0.9
```

This format generalizes — each task type has canonical golden tasks that test *the ability of the text to do its job*, not proxies.

### 2.5 The Signal Density Curve

**Definition**:
For a fixed (text `T`, task type `τ`), the Signal Density Curve is the function:

```
f(ρ) = pass_rate( compress(T, τ, target_density=ρ) )
```

where `ρ ∈ (0, 1]` is the target compression ratio (compressed tokens / original tokens).

**Empirical claim**: for most inputs, `f` is concave with a peak `ρ*` strictly less than 1.0 (i.e., compressed is better than original) *for a range of `τ`*.

**How we compute it**:
1. Fix `τ`, fix `T`
2. Sweep `ρ` over `[0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]`
3. For each `ρ`, run `compress()` to produce `T_ρ`
4. For each `T_ρ`, run eval harness to measure `f(ρ)`
5. Fit a quadratic (or save raw points) and locate peak

**Output**: the curve (plot + JSON), and `ρ*`.

This is the centerpiece visualization of the project.

### 2.6 Backend abstraction

```python
class Backend(Protocol):
    def compress(self, *, system: str, user: str, max_tokens: int = 4096) -> str: ...
    def name(self) -> str: ...
    def supports_caching(self) -> bool: ...
```

v0.1 ships one implementation (`ClaudeBackend`). v0.3+ can add OpenAI, Gemini, local.

**Important**: we do NOT abstract the prompts. Different backends may need different prompt phrasings. The backend interface accepts a pre-rendered system + user pair; prompt selection happens at a higher layer (`denser.compress`) based on `task_type + backend_type`.

## 3. Anti-goals (what we will NOT do in v0.1)

- Support for non-Claude backends
- Web playground (worth doing — v0.2)
- Claude Code skill that auto-compresses skills (ironically meta — v0.2)
- Cross-model transfer benchmarks (hard, worth doing carefully — v0.3)
- Multi-stage compression pipelines (compress → evaluate → re-compress iteratively)
- Fine-grained compression controls (stylistic knobs beyond `target_density` and `task_type`)
- Chinese-language inputs (support is probably fine but not benchmarked — v0.2)
- Streaming compression API
- Asynchronous batch mode

Scope discipline is how v0.1 ships on time.

## 4. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Compression quality is only marginally better than trivial (rule-based) | Med | Ensure benchmark includes comparison vs. trivial whitespace-strip baseline. If denser < baseline + 10%, reconsider approach |
| Task pass-rate evaluation is noisy (LLM-judge is inconsistent) | High | Aggregate over ≥ 30 trials per compression; use `claude-haiku` as judge (cheap, can afford n=100); publish the eval methodology so others can verify |
| People dismiss as "just another LLM-wrapping tool" | High | **The whitepaper is the answer to this.** Write it paper-quality. Coin the Signal Density Curve term and make it the headline. |
| Signal Density Curve claim doesn't hold empirically | Low | Measure first. If `f` is monotone (no peak for most inputs), drop the curve framing and reposition as "aggressive but safe compression." Scope back, not up. |
| Claude API is down during launch week | Low | Haiku fallback in the CLI; pre-cache benchmark results so README numbers render even if live API fails |
| Someone (LangChain, LlamaIndex) ships similar tool first | Med | Speed + quality of execution is our answer. Ship v0.1 in 4 weeks, then iterate rapidly. Don't burn months on v0.2 before launching |

## 5. Launch messaging

### Hero statement
> "Most prompt compression tools tell you the output is shorter. `denser` tells you it's **better** — and proves it on 30 real tasks."

### Three bullet pitch
- **Task-typed**: the sweet spot density differs for skills, system prompts, and memory entries — denser models all six
- **Eval-first**: every compression comes with a pass-rate delta on real tasks
- **Empirical sweet spot**: plot the Signal Density Curve for your specific input and see the peak

### Landing page first 10 words (critical):
> "Find the signal density sweet spot for your LLM prompts."

### Avoid
- "LLM-powered" (cliché, says nothing)
- "AI-optimized" (same)
- "10x your prompts" (scam-adjacent)
- "GPT-4 compatible" (we do Claude; cross-model is v0.3)

## 6. Success metrics

**Quantitative (4 weeks post-launch)**:
- GitHub stars: 100 baseline / 500 strong / 1k+ viral
- PyPI installs: 500+ / week by end of month 2
- HN front page: one shot, success = staying on front page ≥ 6h
- External citation: at least 1 blog post / tweet by a named practitioner

**Qualitative**:
- The phrase "Signal Density Curve" appears in ≥ 3 independent discussions online
- An Anthropic engineer engages with the project publicly
- An awesome-list maintainer lists it

**Failure signals (to course-correct at)**:
- < 20 stars in first week → README/launch failure, redo messaging
- Eval numbers are contested → write a stronger methodology doc
- Nobody uses the CLI → the CLI is too abstract, add recipes

## 7. Immediate next actions (this session)

1. `PROJECT_PLAN.md` ✓ (this file)
2. `docs/WHITEPAPER.md` — substantive first draft
3. `docs/TAXONOMY.md` — full spec for all 6 task types
4. `denser/taxonomy.py` — typed enum + spec objects
5. `denser/tokens.py` — token counting helpers
6. `denser/backends/base.py` + `denser/backends/claude.py` — Claude Opus 4.6 backend with prompt caching
7. `denser/prompts/skill.py` — first task-typed compression prompt (production-grade)
8. `denser/prompts/registry.py` — `TaskType → prompt` mapping
9. `denser/compress.py` — main API
10. `denser/cli.py` — `denser compress` command functional
11. One golden before/after pair in `examples/skills/`
12. `tests/test_taxonomy.py` — basic passing test
13. `.github/workflows/ci.yml`

After this session, the repo is **installable, runnable, and tested** — not just a README and wishlist.
