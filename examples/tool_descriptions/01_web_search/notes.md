# Notes: web_search tool description compression

**Original**: 330 words (~430 tokens)
**Compressed**: 62 words (~80 tokens)
**Density**: 0.19 (81% savings)
**Task-type sweet spot for `tool_description`**: 0.45 – 0.60

Below the typical sweet spot because the original is unusually verbose — parameter tables duplicate the schema, and the examples list is illustrative rather than load-bearing.

## Preserved

- One-line purpose — what the tool does
- "Use when" trigger condition
- "Do NOT use for" anti-trigger with examples (these are the most operationally useful lines)
- Rate limit (50/hour) — a non-obvious failure mode
- "Over-broad queries" quirk — behavior hint that wouldn't be inferable
- Return format — a single line covers it

## Stripped

- Parameter table — already declared in the JSON schema adjacent to the description
- "Please provide a clear query" courtesy — implied
- "Examples of good queries" — five specific queries that don't add information beyond "be specific"
- Redundant don't-use examples — consolidated into anti-trigger category

## Risk check

- The stripped parameter explanations might help a weaker model choose appropriate defaults. Pilot eval on 50 invocation decisions showed no regression with Claude Sonnet 4.6; untested on weaker models.
- **Safety preservation**: the `safe_search=true` default is in the schema, not removed.
