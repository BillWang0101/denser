---
name: denser-compress
description: Produce a shorter candidate for a skill, system prompt, tool description, memory entry, CLAUDE.md, or one-shot doc using role-aware rewrite guidance. Use when user asks to compress / shorten / denser-ify a prompt-like file. Do NOT use for general summarization, code, commit messages, or creative writing.
---

# denser-compress

Input: a file path, inline code block, or (optional) `task_type`. If task_type is absent, infer via the tree below. If ambiguous, ask ONE yes/no question.

## Decision Tree

```
Loads once, discarded?                 → one_shot_doc
File in memory/ directory?             → memory_entry
`description` field in tool schema?    → tool_description
Activated conditionally by trigger?    → skill
Prefixed to every call?                → system_prompt
CLAUDE.md (or equivalent)?             → claude_md
```

## Workflow

1. Read input (Read tool for files).
2. Read `REFERENCE_taxonomy.md` for preserve/strip rules and the exploratory generation range; the range is not a behavior guarantee.
3. Compress per those rules. Use MUST/NEVER/DO NOT for hard constraints. Preserve YAML frontmatter and navigational headers verbatim.
4. Emit this exact report (no preamble):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     <filename>  ->  compressed
     <N> tokens  ->  <M> tokens   (-<X>%)
     density: <ratio>   (exploratory range: <range>)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ### What was stripped
   - <category> — <rationale>   (3-6 bullets)

   ### Compressed output
   ```<compressed text>```
   ```

5. Verify every Preserve item; restore anything missing. This is structural, not proof of behavior preservation.
6. Ask: "Write compressed version to `<path>`? [y/N]". Default NO. Write only if user confirms.

## Hard constraints

- MUST preserve anything marked MUST / NEVER / CRITICAL / IMPORTANT / safety / auth in the input.
- MUST NOT invent content not in the original.
- NEVER write to a file without explicit user confirmation.
- NEVER compress files < 100 tokens, code, or binaries — abort with a note.
- If input is not prompt-like LLM input (news, chat, prose, creative writing), decline.
