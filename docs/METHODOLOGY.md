# Compression Methodology

> How denser actually decides what to cut.

The [taxonomy](TAXONOMY.md) tells you *what* to preserve and strip for each task type — categorical rules, static. This document tells you *how* to apply those rules in the middle of a real compression — the moment-to-moment judgment that turns a list of rules into a finished compressed text.

The methodology has four layers. Every compression — by the CLI, by the Claude Code skill, by a human contributor writing a new example pair — walks them in order.

---

## Layer 1 — Three framing questions for every piece of content

For every sentence, every bullet, every paragraph in the original text, ask three questions in this order:

### 1. Does removing this break a downstream decision?

If an LLM executes based on this text, and you remove this content, does any decision the LLM makes become wrong or ambiguous?

- **Yes** → load-bearing. Preserve.
- **No** → candidate for removal. Continue to question 2.

### 2. Is the information already implied elsewhere?

Is the same fact (or something that reliably produces the same behavior) present:
- In the adjacent schema (for `tool_description` — the parameter types are in the JSON schema)?
- In the code structure (for `claude_md` — file tree is visible via `ls`)?
- In the LLM's base training (for any type — "be honest", "be helpful" are defaults)?
- Earlier in this same text?

If any "yes" → this content is a restatement. Remove.

### 3. Who actually uses this — the LLM, or a human reader?

- LLM uses it → preserve (even if stylistically ugly)
- Only a human reader browsing the file will benefit → remove (at runtime, no human is reading)

Skills are executed, not read. Written-for-human framing is the single biggest source of low-signal tokens in the average skill.

**Rule**: A piece of content must pass all three questions (load-bearing + not implied + LLM-used) to survive.

---

## Layer 2 — Five macro moves

In descending order of how often each move applies:

### 1. Strip motivational and meta commentary

Delete sentences like:
- "You are a helpful assistant that does X."
- "The purpose of this skill is Y."
- "It's important to Z."
- "Remember, the goal is W."

The LLM is already executing this skill in the context of the user's request. It does not need to be told what it is doing or why the skill exists. These sentences serve the human author at write time, not the LLM at run time.

### 2. De-duplicate cross-section overlap

Walk the document top to bottom. For each rule, check whether it appears again in a different section (phrased differently). Keep the strongest-phrased version, delete the rest.

**Strength hierarchy** for rules:
1. `MUST` / `NEVER` / `DO NOT` (imperative negation with all-caps)
2. `Do this` / `Don't do this` (imperative)
3. `Prefer this` / `Avoid this` (preferential)
4. `X is recommended` / `X should be avoided` (descriptive)

When the same rule appears at different strengths, keep the strongest.

### 3. Compress "listed enumeration" into "pattern rule"

If you see 4+ bullets that are variations of the same idea, replace them with the rule that generates them.

```
BEFORE:
- A file path
- Inline text in a code block
- A string passed via stdin
- Text copied from chat

AFTER:
- Input: any text, from any source
```

LLMs reliably expand patterns. The reverse doesn't work (lists can't be reconstructed from pattern-less prose), so pattern is the compressed form.

### 4. Collapse explanation clauses into imperatives

`A, because B` → `A`.

An LLM doesn't need the reason to execute the rule; it just needs the rule. The reason is for human review.

**Exception**: if B changes how edge cases are judged. For example:

- `NEVER use mocks in integration tests, because last quarter's migration broke when mocks diverged from prod` — the reason here is load-bearing, because it tells the LLM what to do when someone proposes relaxing the rule ("this test can mock because X is stable" → no, the reason applies).
- `NEVER use mocks in integration tests, because it's cleaner` — the reason here adds no executable guidance. Strip.

The test: **if I only had the compressed text, would I make a wrong judgment on an edge case the original handled correctly?** If yes, keep the reason. If no, strip it.

### 5. Replace examples with rules; keep examples only for traps

Examples serve two roles:
- **Happy-path demonstration** — "here's how this works in the normal case." → **strip**. The rules already cover normal cases.
- **Trap demonstration** — "here's the non-obvious edge case that breaks if you forget it." → **keep**. These earn their tokens.
- **Output format contract** — "the output must look exactly like this." → **keep**. Format contracts need concrete instances.

When in doubt: ask whether the example's absence would make an LLM fail in a non-obvious way. If not, strip.

---

## Layer 3 — Sentence-level tactics

After Layer 2 has trimmed sections, apply these mechanical substitutions to the surviving sentences.

| Before | After | Why |
|---|---|---|
| "Please do X" / "You might want to X" / "It would be good to X" | "X" or "MUST X" | RLHF-trained models obey imperatives and MUST more reliably than polite phrasings |
| "Don't do Y" / "Avoid Y" | "NEVER Y" / "DO NOT Y" | Negative imperatives in all-caps have lowest execution variance |
| Multi-line YAML `description: \|\n  ...\n  ...` | single-line `description: ...` | YAML parse-equivalent; multi-line is only for human readability |
| "A file path (for example `path/to/thing`), or inline text (which you paste in a code block), or a directory (in which case ask which file)" | "A file path, inline code block, or directory (ask which file)" | Parenthetical examples are usually inferable from the noun |
| Bold/italic emphasis (`**important**`) | Plain text with structural placement | LLM tokenization doesn't benefit from visual markup |
| "The user will provide one of the following options:" + numbered list | "Input:" + comma-separated list | Drop the rhetorical setup; go straight to the content |
| "Count the tokens. The rough estimate is max(chars/4, words*1.3)." as separate step | Mention inline where token count is used | Separate procedural step wastes an entire scaffolded number |

These look small. Applied consistently across a document, they save 15–25% of surviving tokens.

---

## Layer 4 — When to stop

Compression has diminishing returns, and past a point, negative returns. Stop when:

### Signals to stop

1. **Next cut would remove something in the task type's Preserve list.** Don't violate the taxonomy for compression aesthetics.

2. **Next cut would require the LLM to "guess back" load-bearing content.** Compression that the model has to reconstruct under uncertainty is worse than no compression.

3. **Density has reached the task type's sweet-spot midpoint.** Further compression has low expected EV and rising risk. The sweet spot is the sweet spot; respect it.

4. **A MUST or NEVER is about to be modified.** Stop immediately. Safety and explicit hard constraints are never the compression target, even when they're verbose.

### Signals to continue

1. Density is still above the sweet-spot *upper bound*.
2. Remaining text still contains motivational preamble, duplicate rules, or happy-path examples.
3. Remaining sentences still use "please" / "might" / "could consider" for what are actually hard rules.

### The meta-rule

> **When in doubt, stop.** An under-compressed text is forgivable. An over-compressed text that deletes a load-bearing rule is a failure we refuse to ship.

---

## First-principles grounding

This methodology is not invented from scratch. It combines five established ideas:

### 1. Shannon information theory
Information is surprise — content that cannot be reconstructed from context. Content that *can* be reconstructed is, by definition, redundant. LLMs reconstruct broadly, which means more content is implicitly redundant for them than for humans.

### 2. Grice's maxim of Quantity
Say as much as needed; no more. Cooperative communication treats excess as dishonest (it implies the excess matters when it doesn't) and under-communication as obstructive.

### 3. Transformer attention mechanics
Attention is softmax-normalized across the context. Each additional token consumes a fraction of the attention mass available to the others. Decorative tokens don't just fail to contribute — they actively dilute load-bearing content's attention share.

### 4. RLHF reliability distributions
LLMs trained with RLHF respond to imperative commands, all-caps emphasis, and negative constraints with lower response variance than they do to hedges, pleasantries, or preferential phrasings. Using MUST / NEVER / DO NOT is not stylistic; it's variance-reducing.

### 5. Information-theoretic Occam's Razor
Of two texts that produce the same behavior in the LLM, prefer the one with fewer tokens. The savings compound in high-frequency cases (skills loaded per turn, system prompts prefixed per call).

---

## Using this methodology

### As a contributor

When you submit a new example pair to `examples/`, use this methodology to write `notes.md`. Describe which Layer 2 moves you applied, which Layer 3 tactics triggered, and why you stopped where you did.

### As a practitioner

When hand-compressing your own skills and prompts, walk the four layers in order:
1. Layer 1 for every section — *is this content earning its tokens?*
2. Layer 2 for the whole doc — *are there patterns of waste across sections?*
3. Layer 3 per surviving sentence — *small token savings, consistently applied.*
4. Layer 4 to decide when to stop.

### As a reviewer

When reviewing someone else's compressed text, check in this order:
1. Did they preserve everything in the task type's Preserve list?
2. Did they drop below the sweet-spot lower bound? If so, did they document why?
3. Did they strip load-bearing content for aesthetic compression? (Layer 1 question 1 failure)
4. Did any MUST / NEVER rule get softened or removed?

If any "yes" in 3–4, reject. If sweet-spot violation without documentation, ask for notes.

---

## Example: the self-compression case study

We compressed denser's own Claude Code skill (`denser-compress/SKILL.md`) using this methodology. Result: **1249 → 526 tokens (-58%)**, density 0.42, inside the skill sweet spot (0.30 – 0.45), with all preserve-list categories intact.

See [`examples/skills/02_denser_compress_self/`](../examples/skills/02_denser_compress_self/) for the full before/after and a line-by-line methodology walkthrough.

---

## Revision history

- **v0.1 (2026-04-15)** — initial methodology extracted from the self-compression session that produced `SKILL.compressed.md`. Methodology will be refined as more compressions reveal new moves and new stopping criteria.
