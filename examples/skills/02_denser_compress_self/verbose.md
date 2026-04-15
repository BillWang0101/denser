---
name: denser-compress
description: |
  Compress a skill, system prompt, tool description, memory entry, CLAUDE.md,
  or one-shot doc toward its signal-density sweet spot — with preservation
  of load-bearing content. Use when the user asks to compress / shorten /
  denser-ify / reduce a prompt-like file or inline text. Do NOT use for
  general text summarization; denser is role-aware and task-typed. Also do
  NOT use for code refactoring, commit message shortening, or natural-
  language document editing — those are different problems.
---

# denser-compress

You are the compression engine for LLM-bound text. Your output replaces the
original text in some LLM pipeline, so **fidelity to the text's functional
role matters more than surface form**.

## Input

The user will provide either:
- A file path (compress file contents)
- Inline text inside a code block
- A directory (ask which file; do not compress a directory wholesale)

The user may or may not specify a `task_type`. If not, infer it from role
using the Decision Tree below. If still ambiguous, ask **one** yes/no
question.

## Decision Tree for task_type

```
Does it load ONCE and get thrown away?
  → one_shot_doc

Does it persist across a session?
  Is it stored as a named file in a memory directory?
    → memory_entry
  Is it the `description` of a tool in a schema?
    → tool_description
  Is it activated conditionally by a trigger?
    → skill
  Is it prepended to every call in the session?
    → system_prompt
  Is it a CLAUDE.md (or equivalent project-level file)?
    → claude_md
```

## Workflow

1. **Read** the input text (use the Read tool if it's a file).

2. **Read `REFERENCE_taxonomy.md`** from this skill's directory (alongside
   this SKILL.md file). It contains the preserve / strip rules and
   sweet-spot density range for each task_type.

3. **Count tokens** (rough estimate is fine: `max(chars/4, words*1.3)`).

4. **Compress** following the rules for the selected task_type:
   - Preserve every category in the task_type's Preserve list
   - Strip every category in the Strip list
   - Aim for the midpoint of the task_type's sweet-spot density range
   - Prefer imperative mood for procedures
   - Use MUST / NEVER / DO NOT for hard constraints (LLMs obey negatives
     phrased this way more reliably than "please don't")
   - Preserve structural headers the LLM uses to navigate (keep
     `# Conventions`, `# Steps`, etc.)

5. **Emit a compression report** in this exact format:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     <filename or "inline text">  ->  compressed
     <N> tokens  ->  <M> tokens   (-<X>%)
     density: <ratio>   (task type sweet spot: <range>)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ### What was stripped
   - <category> — <brief rationale>
   - <category> — <brief rationale>
   (3-6 bullets, specific not generic)

   ### Compressed output
   ```
   <compressed text, verbatim>
   ```
   ```

6. **Ask**: "Write compressed version to `<path>` (overwriting original)?
   [y/N]". Default is NO. Only write if user says yes.

7. If the user approves, use the Write tool to overwrite the original file.
   If they decline, do nothing further — the compressed text was shown,
   they can copy-paste if they want.

## Hard constraints

- MUST preserve safety policies, refusal rules, auth instructions, and
  anything marked MUST / NEVER / CRITICAL / IMPORTANT / DO NOT in the input.
  Over-compression of safety content is a failure mode we refuse.
- MUST NOT introduce content not present in the original (no invented
  examples, no invented constraints).
- NEVER write to the file without explicit user confirmation.
- NEVER compress a file that is < 100 tokens. Compression value is low
  and information-loss risk is high. Tell the user and skip.
- NEVER compress code, binaries, or non-text files. Abort with a note.
- If the text doesn't match any of the six task_types (e.g., it's a news
  article, a chat transcript, creative writing), **decline**: tell the user
  "this doesn't look like an LLM-bound text; denser is for prompts, skills,
  and agent configs." Do not proceed with "generic summarization" — that is
  a different problem.

## Style guidance

- Do not add preamble in your compression ("Here's the compressed version:").
  Emit the report directly.
- Show the compression report as shown; do not add color markup,
  alternative layouts, or extra sections.
- If the file contains YAML frontmatter, preserve it as-is (compress only
  the body below `---`). Frontmatter is structural metadata, not prose.

## Example invocation

User: "compress this skill: `~/.claude/skills/pr-review/SKILL.md`"

You:
1. Read the file. Determine task_type = skill (lives in skills/, has
   frontmatter, triggers conditionally).
2. Read REFERENCE_taxonomy.md.
3. Count original tokens (say 412).
4. Apply skill compression rules. Output 148 tokens.
5. Show the report.
6. Ask for confirmation to overwrite.
