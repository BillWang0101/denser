# Taxonomy reference

This file is **auto-generated** from `denser/taxonomy.py`. Do not edit by
hand — run `python scripts/sync_skill_reference.py` after changing the
Python source.

The `denser-compress` skill reads this file to learn the preserve / strip
rules and sweet-spot density range for each task type.

---

## `skill`

**Role**: A triggerable capability unit. Loaded into context only when the skill's description matches the current request.

**Density sweet spot**: 0.30 – 0.45 (target midpoint: 0.38)

### Preserve

- Trigger conditions (when to activate)
- Anti-triggers (when NOT to activate, and which alternative to prefer)
- Hard constraints (MUST/NEVER/DO NOT rules)
- Output format contracts
- 1-2 canonical examples (common case + most common trap)
- Explicit safety policies or refusal boundaries

### Strip

- Motivational preamble ("This skill helps...", "The purpose of...")
- Redundant examples illustrating the same pattern
- Rationale for why the skill exists (belongs in PR/commit messages)
- Polite hedging ("you might want to", "consider whether")
- Instructions the LLM would follow from base training
- Restatement of constraints already implied

### Canonical compressed form (shape hint, not template)

```
Trigger: <activation condition + negative condition>

Do:
  1. <step>
  2. <step>

Hard constraints:
  - MUST <...>
  - NEVER <...>

Example: <1-2 canonical illustrations>
```

---

## `system_prompt`

**Role**: Persistent context loaded at the start of every LLM call in a session. Establishes role, capability boundaries, and output contract.

**Density sweet spot**: 0.40 – 0.55 (target midpoint: 0.47)

### Preserve

- Role definition (identity, persona)
- Capability boundaries (what it can / cannot do)
- Output format contracts (structure, tone, length norms)
- Non-negotiable domain constraints
- Explicit safety policy and refusal behavior

### Strip

- Effusive framing ("You are the world's best...")
- Redundant do-and-don't pairs
- Instructions embedded in base training ("be honest", "be helpful")
- Repeated safety reminders when one suffices
- Backstory prose that doesn't change behavior

### Canonical compressed form (shape hint, not template)

```
Role: <one-line identity>.

You: <capability statements>.
Do not: <boundary statements>.

Output: <format contract>.

Constraints: <domain rules>.
```

---

## `tool_description`

**Role**: The `description` field of a tool in a tool-use schema. Parsed whenever the LLM considers calling a tool.

**Density sweet spot**: 0.45 – 0.60 (target midpoint: 0.53)

### Preserve

- When to use (triggering conditions)
- When NOT to use (disqualifying conditions + which alternative tool)
- Non-obvious failure modes (side effects, rate limits, quirks)
- Tool interaction notes (prerequisites, combinations)

### Strip

- Parameter explanations that duplicate the schema's type info
- Examples of valid parameter values
- Courtesy language ("please provide", "thank you for")
- Restatement of the tool name

### Canonical compressed form (shape hint, not template)

```
<one-line purpose>. Use when: <trigger>. Do NOT use for: <anti-trigger, prefer X>.

Failure modes: <surprises>
```

---

## `memory_entry`

**Role**: A single file in a file-based memory system. Loaded on demand when retrieval surfaces it as relevant.

**Density sweet spot**: 0.58 – 0.78 (target midpoint: 0.68)

### Preserve

- The core fact (the assertion being remembered)
- The "why" (reason or source making it load-bearing)
- The "when to apply" (relevance conditions)

### Strip

- Example scenarios beyond the minimum needed for the "when" rule
- Narrative framing ("I remember that we decided...")
- Timestamps unless the fact is time-bounded
- Cross-references to other memories (belongs in index)

### Canonical compressed form (shape hint, not template)

```
<the fact>

Why: <reason>
When to apply: <conditions>
```

---

## `claude_md`

**Role**: A project-level CLAUDE.md file loaded per-session by Claude Code. Contains conventions, constraints, and local-to-project instructions.

**Density sweet spot**: 0.35 – 0.50 (target midpoint: 0.42)

### Preserve

- Non-obvious conventions (things the LLM would not infer from repo structure)
- Hidden constraints (e.g., "we cannot use library X")
- Project-specific policies
- Decision boundaries (autonomous vs. confirm-first)

### Strip

- API documentation (available in code)
- File structure descriptions (available via `ls`)
- Build/run instructions already in README.md
- Default LLM behaviors ("be helpful", "write tests")
- Duplicates of the same rule phrased differently

### Canonical compressed form (shape hint, not template)

```
# Conventions
- <non-obvious rule>
- <non-obvious rule>

# Constraints
- <hidden constraint>

# Decision boundaries
- <what requires confirmation>
```

---

## `one_shot_doc`

**Role**: A briefing document handed to an LLM once to accomplish a specific task. Examples: implementation spec, code review brief, research summary.

**Density sweet spot**: 0.40 – 0.60 (target midpoint: 0.50)

### Preserve

- Actionable instructions (imperative form)
- Decision criteria for judgment calls on ambiguity
- Acceptance criteria (how to know when done)
- Edge case handling
- Structural headers the LLM can navigate during execution

### Strip

- Motivational preamble about why the project matters
- Background context the LLM can infer from the codebase
- Summary sections that restate detailed content
- Speculative "future work" unless it affects current decisions

### Canonical compressed form (shape hint, not template)

```
# Goal
<what success looks like>

# Steps
1. ...
2. ...

# Decision criteria
- <judgment call> → <how to decide>

# Acceptance criteria
- <testable completion signal>
```

---
