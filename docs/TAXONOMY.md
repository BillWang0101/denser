# Task Type Taxonomy

`denser` models six task types. Each task type drives a different compression strategy, sweet-spot density range, and evaluation golden-task set.

This document is the **operational reference**. For the theoretical framing, see [`WHITEPAPER.md`](WHITEPAPER.md).

---

## Quick reference

| `TaskType` | Typical density peak `ρ*` | Role in LLM pipeline |
|---|---|---|
| `skill` | 0.30 – 0.45 | Triggerable capability unit (Claude Code skills, Agent SDK skills) |
| `system_prompt` | 0.40 – 0.55 | Persistent role/contract prefix |
| `tool_description` | 0.45 – 0.60 | `description` field in a tool-use schema |
| `memory_entry` | 0.58 – 0.78 | A single file in a persistent memory store |
| `claude_md` | 0.35 – 0.50 | Project-level instructions in `CLAUDE.md` |
| `one_shot_doc` | 0.40 – 0.60 | Implementation spec, briefing doc, task handoff |

---

## `skill`

### Role
A triggerable capability unit. The harness loads the skill's body into the LLM's context only when the skill's description matches the current request. The body then instructs the LLM on how to perform that capability.

### Compression profile
**Aggressive.** Peak `ρ*` ≈ 0.30 – 0.45.

### Preserve

1. **Trigger conditions** — when the skill should activate, with examples of matching requests.
2. **Anti-triggers** — when the skill should NOT activate, especially when another similar skill or built-in should be used instead.
3. **Hard constraints** — `MUST`/`NEVER`/`DO NOT` rules that shape behavior.
4. **Output format contracts** — if the skill produces structured output, the schema is load-bearing.
5. **1–2 canonical examples** — one for the common case, one for the most common trap.
6. **Safety policies** — any explicit refusal or redirection rules.

### Strip

- Motivational preamble ("This skill helps Claude by...", "The purpose of this skill is...")
- Redundant examples that illustrate the same pattern
- Explanation of *why* the skill exists (rationale belongs in PR/commit messages, not runtime prompt)
- Polite hedging ("you might want to", "consider whether")
- Instructions the LLM would follow from base training ("be helpful", "be concise")
- Restatement of constraints already implied by earlier rules

### Canonical compressed form

```
Trigger: <clear activation condition + negative condition>

Do:
  1. <step>
  2. <step>
  ...

Hard constraints:
  - MUST <...>
  - NEVER <...>

Example: <1–2 canonical illustrations>
```

### Evaluation golden tasks
- **Trigger accuracy**: given N sample requests (mix of matches and non-matches), does the LLM correctly decide to invoke the skill?
- **Constraint obedience**: does the LLM respect hard constraints when executing the skill body?
- **Output format compliance**: when the skill specifies an output format, does the LLM produce it?

---

## `system_prompt`

### Role
Persistent context loaded at the start of every LLM call in a session. Establishes role, capability boundaries, and output contract.

### Compression profile
**Moderate.** Peak `ρ*` ≈ 0.40 – 0.55.

### Preserve

1. **Role definition** — what the LLM is (agent identity, persona)
2. **Capability boundaries** — what it can and cannot do
3. **Output format contracts** — structure, tone, length norms
4. **Non-negotiable constraints** — domain-specific rules
5. **Safety policy** — refusal behaviors, escalation paths

### Strip

- Effusive framing ("You are the world's best...", "You are extraordinarily skilled at...")
- Redundant do-and-don't pairs (pick one form per rule)
- Instructions embedded in base training ("be honest", "don't make things up" — the model does this by default)
- Repeated safety reminders when one suffices
- Backstory prose that doesn't change behavior

### Evaluation golden tasks
- **Role consistency**: does the LLM maintain the declared persona across test prompts?
- **Boundary enforcement**: does the LLM decline out-of-scope requests?
- **Format compliance**: does output match declared structure?

---

## `tool_description`

### Role
The `description` field of a tool in a tool-use schema. Parsed by the LLM whenever it considers whether to call a tool.

### Compression profile
**Aggressive** for the prose portion. Peak `ρ*` ≈ 0.45 – 0.60.

### Preserve

1. **When to use** — triggering conditions in user-facing language
2. **When NOT to use** — disqualifying conditions, and which alternative tool to prefer
3. **Non-obvious failure modes** — side effects, rate limits, quirks
4. **Tool interaction notes** — "must call X before this", "combines with Y"

### Strip

- Parameter explanations that duplicate the schema's type info
- Examples of valid parameter values (the schema has types; examples rarely help)
- Courtesy language ("please provide", "thank you for")
- Restatement of the tool name

### Canonical compressed form

```
<one-line purpose>. Use when: <trigger>. Do NOT use for: <anti-trigger, prefer X>.

Failure modes: <surprises>
```

### Evaluation golden tasks
- **Invocation accuracy**: given test prompts, does the LLM call the tool when it should and abstain when it shouldn't?
- **Correct alternative selection**: when the tool is wrong but a sibling tool is right, does the LLM pick the sibling?

---

## `memory_entry`

### Role
A single file in a file-based memory system (e.g., the `memory/` directory of a Claude Code session). Loaded on demand when retrieval surfaces it as relevant.

### Compression profile
**Conservative.** Peak `ρ*` ≈ 0.58 – 0.78.

Memory entries are short to begin with, and their value often lives in the "why" that enables edge-case judgment. Over-compression is risky.

### Preserve

1. **The core fact** — the assertion being remembered
2. **The "why"** — the reason or source that makes it load-bearing
3. **The "when to apply"** — conditions under which the fact is relevant

### Strip

- Example scenarios beyond what's needed for the "when to apply" rule
- Narrative framing ("I remember that we decided...")
- Timestamps unless the fact is time-bounded
- Cross-references to other memory entries (use the index file for that)

### Evaluation golden tasks
- **Recall accuracy**: given test scenarios where the memory is relevant, does the LLM apply it correctly?
- **Non-application accuracy**: given test scenarios where the memory is irrelevant, does the LLM refrain from applying it?

---

## `claude_md`

### Role
A project-level `CLAUDE.md` file loaded per-session by Claude Code. Contains conventions, constraints, and local-to-project instructions.

### Compression profile
**Moderate-aggressive.** Peak `ρ*` ≈ 0.35 – 0.50.

`CLAUDE.md` files accumulate cruft: every "from now on" edit adds a line, but nobody prunes. Aggressive compression reveals what's actually load-bearing.

### Preserve

1. **Non-obvious conventions** — things the LLM would not infer from the repo structure
2. **Hidden constraints** — e.g., "we cannot use library X because of license issue"
3. **Project-specific policies** — e.g., "all commits include an issue reference"
4. **Decision boundaries** — what requires user confirmation vs what the LLM can do autonomously

### Strip

- API documentation (available in code)
- File structure descriptions (available via `ls`)
- Build/run instructions that are already in `README.md`
- Default instructions the LLM would follow anyway ("be helpful", "write tests")
- Duplicates of the same rule phrased differently

### Evaluation golden tasks
- **Convention application**: does the LLM apply project conventions when editing/generating code?
- **Constraint respect**: does the LLM avoid prohibited operations?

---

## `one_shot_doc`

### Role
A briefing document handed to an LLM or agent once to accomplish a specific task. Examples: implementation spec, code review brief, research summary.

### Compression profile
**Moderate.** Peak `ρ*` ≈ 0.40 – 0.60.

One-shot docs are not reloaded, so per-token cost is paid once. But the LLM *executes* from them, so instruction clarity is paramount.

### Preserve

1. **Actionable instructions** — what to do, in imperative form
2. **Decision criteria** — how to make judgment calls when the spec is ambiguous
3. **Acceptance criteria** — how to know when the task is done
4. **Edge case handling** — what to do when things go wrong
5. **Structure** — section headers help the LLM navigate during execution

### Strip

- Motivational preamble about why the project matters
- Background context the LLM can infer from the codebase
- Summary sections that will be said again in detail
- Speculative "future work" sections unless they affect current decisions

### Evaluation golden tasks
- **Task completion**: does the LLM produce the expected output?
- **Correct judgment**: does the LLM apply the decision criteria correctly when the spec is ambiguous?

---

## Choosing the right task type

When a text could plausibly be labeled multiple types, use this decision tree:

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

When still ambiguous, run `denser compress` with both candidate types and pick whichever produces higher pass-rate in the eval harness.

---

## Extending the taxonomy

Additional task types are welcomed in future versions. To propose one, open a GitHub issue with:

1. The role the type plays in an LLM pipeline
2. What distinguishes its compression strategy from existing types
3. A sketch of the preserve/strip rules
4. A sketch of 3+ golden evaluation tasks

New types land in a minor version bump when they cover a role not redundant with existing types.
