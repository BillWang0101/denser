# denser integrations

Drop-in integrations for common developer workflows. Each subdirectory target is optional — denser itself doesn't require any of them.

## Pre-commit hook

Print an advisory size review for recognized LLM instruction files (skills,
`CLAUDE.md`, system prompts, memory entries, and tool descriptions). The hook
never blocks a commit because a file is long.

### Installation (Unix / macOS)

From a git repo where you want the check:

```bash
# Pull denser's hook into this repo
curl -sSL https://raw.githubusercontent.com/Evostructs/denser/main/integrations/pre-commit-hook.sh \
    -o .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Or if you have denser cloned locally:

```bash
cp /path/to/denser/integrations/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Installation (Windows)

Most Windows git installs run hooks via Git Bash, so the `.sh` variant usually works directly. If your setup runs PowerShell hooks, use `pre-commit-hook.ps1` instead.

### What it checks

On every `git commit`, the hook:

1. Lists files staged for this commit
2. Filters to LLM-input-shaped paths (see regex in hook scripts)
3. Runs `python -m denser.precommit <files>` to estimate each recognized file's size
4. Prints a review suggestion when a file exceeds an alpha reference size
5. Returns success; length alone is never treated as a behavior failure

### Task-type inference

The hook infers task type from path, not content:

| Path pattern | Task type |
|---|---|
| `skills/*.md` or `.claude/skills/*/*.md` | `skill` |
| `memory/*.md` | `memory_entry` |
| `CLAUDE.md` (any depth) | `claude_md` |
| `*system_prompt*.md` / `*system-prompt*.md` | `system_prompt` |
| `tools/*.md` or `tools/*.json` | `tool_description` |
| *(anything else)* | skipped |

Inference is deliberately narrow — we'd rather miss than false-positive.

### Advisory reference sizes

File sizes at or above these values trigger a review message:

| Task type | Review reference (estimated tokens) |
|---|---:|
| `skill` | 800 |
| `system_prompt` | 600 |
| `tool_description` | 300 |
| `memory_entry` | 250 |
| `claude_md` | 1000 |
| `one_shot_doc` | 1500 |

These are conservative review prompts for the alpha integration. The bundled
corpus is too small to establish optimal lengths, and a longer file may be
entirely correct. Future behavior gates will rely on project-specific contracts
and tests rather than global size limits.

### Bypass

```bash
SKIP_DENSER=1 git commit -m "legitimate large config"
```

### Output example

```
$ git commit -m "update skill"
OK:      skills/pr-review.md (412 tokens, type=skill)
REVIEW:  skills/new-skill.md (850 estimated tokens, type=skill; advisory reference 800, commit allowed)
REVIEW:  skills/monolith.md (1340 estimated tokens, type=skill; advisory reference 800, commit allowed)
```

### Why no API call here

The pre-commit path is hot — it runs on every commit. An API-based check
would add seconds of latency and require configuring an API key per repo.
This hook uses only local token estimation to make size growth visible.

For quality validation, use asset-specific behavior tests. The built-in
`denser eval` fixtures currently provide structural checks only.
