# Introducing denser — historical launch draft

> **Historical launch draft — not current product documentation.** Several
> comparative and empirical statements below were written before the committed
> evidence existed. Do not publish this draft as-is. See [`DESIGN.md`](DESIGN.md)
> and the repository README for the current positioning.

*Draft — to be published at launch.*

---

Every time you load a skill into Claude, a system prompt into GPT, or a memory entry into an agent's context, you are making a quiet bet: that the words you wrote carry enough signal to be worth the tokens they consume, and not so much noise that they pull attention away from what the model needs to do its job.

Most of us lose that bet. Skills accumulate motivational preamble. System prompts carry phrases like "You are the world's best" that describe the model's persona with zero new information. `CLAUDE.md` files grow every time someone adds a "from now on" rule and never shrink. Tool descriptions repeat the parameter schema in prose.

This can affect cost, context use, and maintenance, but the direction and size of
the behavioral effect depend on the asset, model, workload, and cache behavior.

Existing work already covers token pruning, structured prompt optimization,
evaluation, and runtime context management. denser's narrower opportunity is
version-controlled instruction assets with role-specific evidence and review.

The original launch draft organized denser around three ideas:

### 1. Task-typed compression

A skill, system prompt, and project instruction play different roles and have
different failure modes. The early density ranges were generation defaults,
not measured optima.

denser models six task types explicitly. For each, it encodes preserve / strip rules derived from the role that type plays. When you compress a skill, denser knows the trigger condition is load-bearing and the "this skill helps by..." preamble is not. When you compress a memory entry, it knows the "why" behind the fact is load-bearing and the narrative reminiscence around it is not.

### 2. Eval-first methodology

denser ships an early evaluation harness. Its current built-in fixtures check
for structural signals; real trigger, boundary, tool, and output behavior still
requires asset-specific cases.

An observed fixture score is diagnostic and does not by itself prove behavior
preservation or improvement.

### 3. The Signal Density Curve

This is the idea that I think will outlast whatever shape denser's code takes.

Take any LLM-bound text and any task it's supposed to do. Sweep several compression ratios. Measure task pass-rate at each. Plot the pairs.

The original hypothesis predicted a concave curve with an interior best point.
The committed evidence does not currently establish that claim; observed shapes
may be monotone, flat, noisy, multi-peaked, or favor the original.

denser can plot observed points and an optional descriptive quadratic fit. That
plot is exploratory, not a production-safe optimum.

The useful framing is that both "shorter is better" and "more detail is safer"
are testable claims. Concavity is one hypothesis to test, not an assumption.

### What's in v0.1

- Python library + CLI installable from source
- Claude Opus 4.6 as the default compression backend (with prompt caching)
- Six task types: `skill`, `system_prompt`, `tool_description`, `memory_entry`, `claude_md`, `one_shot_doc`
- 11 built-in structural fixture files
- 8 curated before/after examples documenting rewrite decisions
- A development runner for the small bundled corpus
- A whitepaper retained as a corrected research hypothesis

### What's next

v0.2 will add a Claude Code skill that compresses *other* skills (irony intended), pre-commit hooks, and a web playground. v0.3 will add OpenAI and Gemini backends to enable cross-model transfer studies. v0.4 will add local model backends for users who don't want to depend on a cloud API.

Most importantly, I want the Signal Density Curve framing to become something practitioners reach for when reasoning about prompt design. Not as a denser-specific concept, but as a shared mental model: your prompt isn't at its best because you wrote it — your prompt is at its best when it hits the peak of the curve, wherever that peak happens to be.

### Try it

```bash
git clone https://github.com/Evostructs/denser.git
cd denser
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...
denser compress --type skill my_skill.md
```

Repository: [github.com/Evostructs/denser](https://github.com/Evostructs/denser)
Whitepaper: [`docs/WHITEPAPER.md`](https://github.com/Evostructs/denser/blob/main/docs/WHITEPAPER.md)
Cookbook: [`docs/COOKBOOK.md`](https://github.com/Evostructs/denser/blob/main/docs/COOKBOOK.md)

Contributions welcome — especially new golden tasks, sample pairs across domains, and cross-model transfer experiments.

---

*— Bill Wang*
