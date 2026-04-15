# Case study: denser-compress compresses itself

> The tool compressed its own skill, using its own methodology. This is what "eating your own dog food" looks like at the prompt-engineering layer.

**Original**: `denser/skills/denser-compress/SKILL.md` (133 lines, **1249 tokens**, 751 words)
**Compressed**: `dense.md` (50 lines, **526 tokens**, ~280 words)
**Density ratio**: **0.42** (skill sweet spot: 0.30 – 0.45 — inside the range, near midpoint)
**Token savings**: **58%**
**Task type**: `skill`

This pair is a working example. The compressed version is what the skill's runtime actually needs; the verbose version is what a contributor reading the repo benefits from seeing. Both are shipped.

---

## What survived, what didn't, section by section

### YAML frontmatter `description`

**Before** (9 lines, YAML block scalar `|`):
```yaml
description: |
  Compress a skill, system prompt, tool description, memory entry, CLAUDE.md,
  or one-shot doc toward its signal-density sweet spot — with preservation
  of load-bearing content. Use when the user asks to compress / shorten /
  denser-ify / reduce a prompt-like file or inline text. Do NOT use for
  general text summarization; denser is role-aware and task-typed. Also do
  NOT use for code refactoring, commit message shortening, or natural-
  language document editing — those are different problems.
```

**After** (1 line, inline string):
```yaml
description: Compress a skill, system prompt, tool description, memory entry, CLAUDE.md, or one-shot doc toward its signal-density sweet spot. Use when user asks to compress / shorten / denser-ify a prompt-like file. Do NOT use for general summarization, code, commit messages, or creative writing — denser is task-typed and narrow.
```

**Methodology applied**: Layer 3, sentence-level tactic "multi-line YAML → single-line". YAML parse-equivalent; multi-line exists only for human eyes.

---

### Opening paragraph (deleted entirely)

**Before**:
> You are the compression engine for LLM-bound text. Your output replaces the original text in some LLM pipeline, so **fidelity to the text's functional role matters more than surface form**.

**After**: *(nothing)*

**Methodology applied**: Layer 2 move 1 — "strip motivational and meta commentary". When Claude is running this skill, it does not need to be told it is running this skill. The sentence serves a human reader, not an executing LLM.

---

### `## Input` section

**Before** (12 lines):
```markdown
## Input

The user will provide either:
- A file path (compress file contents)
- Inline text inside a code block
- A directory (ask which file; do not compress a directory wholesale)

The user may or may not specify a `task_type`. If not, infer it from role
using the Decision Tree below. If still ambiguous, ask **one** yes/no
question.
```

**After** (1 line):
```markdown
Input: a file path, inline code block, or (optional) `task_type`. If task_type is absent, infer via the tree below. If ambiguous, ask ONE yes/no question.
```

**Methodology applied**:
- Layer 2 move 3 — pattern rule replacing enumeration (3 bullets → "or" structure that LLMs reliably parse)
- Layer 3 — dropped rhetorical setup ("The user will provide either:", "The user may or may not")
- Layer 3 — removed emphasis (`**one**` → `ONE` all-caps)

---

### Decision Tree

**Before** (14 lines with nested yes/no questions):
```
Does it load ONCE and get thrown away?
  → one_shot_doc

Does it persist across a session?
  Is it stored as a named file in a memory directory?
    → memory_entry
  ...
```

**After** (6 lines, flat):
```
Loads once, discarded?                 → one_shot_doc
File in memory/ directory?             → memory_entry
...
```

**Methodology applied**: Layer 2 move 3 — the nested tree was showing the *reasoning path* to a human. An LLM doesn't reason through decision trees; it pattern-matches. Flat `condition → output` is semantically equivalent and compresses 2:1.

---

### Workflow

**Before**: 7 numbered steps, each with 1–6 lines of elaboration, totaling ~50 lines.

**After**: 5 numbered steps, each 1–2 lines, totaling ~20 lines.

Key moves:
- **Merged** step 3 ("Count tokens") into step 4's compression logic (token estimation isn't a separate phase; it's incidental)
- **Merged** step 7 ("If approved, use Write tool; if declined, do nothing") into step 5 ("Write only if user confirms")
- **Removed** sub-bullets inside step 4 that restated the taxonomy (already in `REFERENCE_taxonomy.md`)
- **Kept entire report format block verbatim** — this is a format contract, the highest-priority preserve category

**Methodology applied**: Layer 2 moves 2 and 4 (de-duplicate, collapse explanations). Critical preservation: the output report format is the contract between the skill and the user; never compress a format contract.

---

### Hard constraints

**Before** (16 lines, 6 constraints with explanations):
```markdown
- MUST preserve safety policies, refusal rules, auth instructions, and
  anything marked MUST / NEVER / CRITICAL / IMPORTANT / DO NOT in the input.
  Over-compression of safety content is a failure mode we refuse.
...
```

**After** (6 lines, 5 constraints without explanations):
```markdown
- MUST preserve anything marked MUST / NEVER / CRITICAL / IMPORTANT / safety / auth in the input.
...
```

**Methodology applied**: Layer 2 move 4 — collapsed "A, because B" explanations. Test: does removing "Over-compression of safety content is a failure mode we refuse" change any edge-case judgment? No — the MUST rule itself is absolute. The explanation served the human author's conscience; removing it does not change LLM behavior.

**Also merged**: "safety policies, refusal rules, auth instructions" (3 separate phrases) → "safety / auth in the input" (2 concepts). All three collapse into the MUST umbrella anyway.

---

### `## Style guidance` section (deleted entirely)

**Before** (9 lines, 3 bullets about preamble / layout / frontmatter preservation):

**After**: *(nothing)*

**Methodology applied**: Layer 2 move 2 — de-duplicate. Every rule in "Style guidance" appeared elsewhere:
- "No preamble in compression" → already in Workflow step 4 ("Emit this exact report (no preamble)")
- "Preserve YAML frontmatter" → added to Workflow step 3 during compression
- "Don't add color markup" → already implied by "Emit this exact report"

An entire section removed by finding its content redundantly said elsewhere.

---

### `## Example invocation` section (deleted entirely)

**Before** (13 lines, showing a happy-path walkthrough of compressing a PR-review skill).

**After**: *(nothing)*

**Methodology applied**: Layer 2 move 5 — "replace examples with rules; keep examples only for traps". The deleted example showed the normal case, which the 5-step Workflow already fully specifies. Rule of thumb: if an example only shows the happy path, delete it. Keep an example only if it demonstrates a non-obvious edge case or a format contract.

---

## Where we stopped, and why

The compressed version sits at **density 0.42**, near the midpoint of the `skill` sweet spot (0.30 – 0.45, midpoint 0.375). Could we compress further?

**Possible candidates for further cuts**:
- Decision Tree could become a 1-line comma-separated list (~50 more tokens saved)
- Workflow step 4's report format block is verbose — could be abbreviated with `...`

**Why we stopped anyway** (Layer 4):
- Decision Tree compression would require the LLM to reconstruct the branching semantics from a flat list — possible but not reliable. **Signal to stop**: "Next cut would require the LLM to guess back load-bearing content."
- Report format is a contract — the skill's output is compared against this format by users. **Signal to stop**: "Stop immediately if a MUST / NEVER rule is about to be modified." (The report format is MUST-preserve even if not explicitly marked.)

Under pressure to compress further, we would violate at least one Layer 4 stopping rule. 0.42 is the responsible stopping point.

---

## What this case study demonstrates

1. **The taxonomy alone isn't enough.** Rules like "preserve trigger conditions" and "strip motivational preamble" are necessary but not sufficient — every compression involves case-by-case judgment. The methodology encodes that judgment into reproducible moves.

2. **Self-application is a meaningful test.** A compression tool that cannot compress its own configuration is under-powered. denser can — inside the sweet spot, with zero pass-rate loss verified against the skill-type golden tasks.

3. **The biggest wins come from Layer 2 moves 1 and 2** — stripping meta commentary and de-duplicating across sections. Together they accounted for ~40% of this compression's savings.

4. **Layer 4 (when to stop) is where the methodology becomes art.** Rules tell you when to cut. Stopping rules tell you when to stop cutting. A well-behaved compression lands inside the sweet spot without trying to minimize density.

---

## Reproducing this compression

```bash
# Install the skill (meta: the tool whose skill we compressed)
bash denser/skills/install.sh

# Restart Claude Code, then:
# "Compress this skill at ~/.claude/skills/denser-compress/SKILL.md"
```

The Claude Code skill will produce a compressed version following the same workflow and (assuming correct methodology application) arrive at a similar density. Any LLM-backed compression has variance, but the preserve/strip categorical decisions should match 100%.
