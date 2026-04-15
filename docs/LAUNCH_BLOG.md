# Introducing denser: Finding the signal density sweet spot for LLM inputs

*Draft — to be published at launch.*

---

Every time you load a skill into Claude, a system prompt into GPT, or a memory entry into an agent's context, you are making a quiet bet: that the words you wrote carry enough signal to be worth the tokens they consume, and not so much noise that they pull attention away from what the model needs to do its job.

Most of us lose that bet. Skills accumulate motivational preamble. System prompts carry phrases like "You are the world's best" that describe the model's persona with zero new information. `CLAUDE.md` files grow every time someone adds a "from now on" rule and never shrink. Tool descriptions repeat the parameter schema in prose.

This isn't a cosmetic problem. It's a measurable one. Transformer attention is softmax over all tokens — every decorative token subtracts from the attention mass available to load-bearing content. The "lost in the middle" effect degrades recall on long contexts. Prompt caching makes long system prompts cheap once, but doesn't solve the attention dilution. And the cost of a verbose skill doesn't just show up in API bills; it compounds across hundreds of turns, thousands of sessions.

Existing prompt compression tools treat this as a generic text problem. [LLMLingua](https://github.com/microsoft/LLMLingua) prunes low-perplexity tokens; various smaller tools strip whitespace and collapse synonyms. None distinguish a skill from a system prompt from a memory entry. None validate that compression actually preserves task performance. None show you *where the sweet spot is* for your specific input.

Today I'm open-sourcing **denser** — a framework built around three ideas the existing tools miss:

### 1. Task-typed compression

A skill is not a system prompt is not a `CLAUDE.md`. They play different roles in an LLM pipeline, they compress to different sweet-spot densities, and they have different content that must be preserved.

denser models six task types explicitly. For each, it encodes preserve / strip rules derived from the role that type plays. When you compress a skill, denser knows the trigger condition is load-bearing and the "this skill helps by..." preamble is not. When you compress a memory entry, it knows the "why" behind the fact is load-bearing and the narrative reminiscence around it is not.

### 2. Eval-first methodology

Most compression tools show you shorter text and let you hope for the best. denser ships with an evaluation harness: give it a compressed version and it runs a set of golden tasks — "does this skill still trigger on the right requests?", "does this system prompt still enforce its boundaries?" — against both the original and the compressed, and reports the pass-rate delta.

If compression hurt task performance, you know immediately. If it improved it (which happens more often than you'd expect), you know that too.

### 3. The Signal Density Curve

This is the idea that I think will outlast whatever shape denser's code takes.

Take any LLM-bound text and any task it's supposed to do. Sweep several compression ratios. Measure task pass-rate at each. Plot the pairs.

For most inputs, you get a concave curve. Peak is rarely at ρ = 1.0 (the uncompressed original). Instead, it lives somewhere between ρ = 0.30 and ρ = 0.70, depending on task type — a sweet spot where enough noise is gone for attention to concentrate, but not so much that load-bearing content has been lost.

denser can plot this curve for your specific text and task type, so you're not relying on industry averages or rules of thumb — you're seeing your input's empirical optimum.

The Signal Density Curve is not a new technique. It's a *framing* — a way to think about prompt engineering as an optimization over a concave function, rather than as a craft. Once you see it that way, a lot of practices change. "Shorter is better" and "more detail is safer" both become testable claims, not preferences.

### What's in v0.1

- Python library + CLI (`pip install denser`)
- Claude Opus 4.6 as the default compression backend (with prompt caching)
- Six task types: `skill`, `system_prompt`, `tool_description`, `memory_entry`, `claude_md`, `one_shot_doc`
- 12 built-in golden tasks covering structural preservation for each type
- 6 curated before/after sample pairs demonstrating the framework in action
- Reproducible benchmarks
- A formal whitepaper documenting the Signal Density Curve methodology

### What's next

v0.2 will add a Claude Code skill that compresses *other* skills (irony intended), pre-commit hooks, and a web playground. v0.3 will add OpenAI and Gemini backends to enable cross-model transfer studies. v0.4 will add local model backends for users who don't want to depend on a cloud API.

Most importantly, I want the Signal Density Curve framing to become something practitioners reach for when reasoning about prompt design. Not as a denser-specific concept, but as a shared mental model: your prompt isn't at its best because you wrote it — your prompt is at its best when it hits the peak of the curve, wherever that peak happens to be.

### Try it

```bash
pip install denser
export ANTHROPIC_API_KEY=sk-ant-...
denser compress --type skill my_skill.md
```

Repository: [github.com/BillWang0101/denser](https://github.com/BillWang0101/denser)
Whitepaper: [`docs/WHITEPAPER.md`](https://github.com/BillWang0101/denser/blob/main/docs/WHITEPAPER.md)
Cookbook: [`docs/COOKBOOK.md`](https://github.com/BillWang0101/denser/blob/main/docs/COOKBOOK.md)

Contributions welcome — especially new golden tasks, sample pairs across domains, and cross-model transfer experiments.

---

*— Bill Wang*
