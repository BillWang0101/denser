# denser integrations

Drop-in integrations for common developer workflows. Each subdirectory target is optional — denser itself doesn't require any of them.

## Pre-commit hook

Block commits that introduce overly-verbose LLM input files (skills, `CLAUDE.md`, system prompts, memory entries, tool descriptions).

### Installation (Unix / macOS)

From a git repo where you want the check:

```bash
# Pull denser's hook into this repo
curl -sSL https://raw.githubusercontent.com/BillWang0101/denser/main/integrations/pre-commit-hook.sh \
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
3. Runs `python -m denser.precommit <files>` to check tokens against each file's task-type sweet-spot ceiling
4. Blocks the commit if any file is over its ceiling by ≥10%

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

### Token ceilings

File sizes above these typical ceilings (with a 10% margin before blocking) trigger the check:

| Task type | Ceiling (tokens) | Blocking threshold |
|---|---:|---:|
| `skill` | 800 | 880 |
| `system_prompt` | 600 | 660 |
| `tool_description` | 300 | 330 |
| `memory_entry` | 250 | 275 |
| `claude_md` | 1000 | 1100 |
| `one_shot_doc` | 1500 | 1650 |

Ceilings come from the observed distribution in `examples/` and the sweet-spot ranges in the taxonomy. They are not hard-coded to your project — override via environment variable `DENSER_PRECOMMIT_CEILING_<TYPE>` (roadmap).

### Bypass

```bash
SKIP_DENSER=1 git commit -m "legitimate large config"
```

### Output example

```
$ git commit -m "update skill"
OK:      skills/pr-review.md (412 tokens, type=skill)
WARN:    skills/new-skill.md (850 tokens, type=skill; consider compressing, typical ceiling 800)
BLOCK:   skills/monolith.md (1340 tokens, type=skill; >= 880 block threshold)
         Run: denser compress --type skill skills/monolith.md

denser: one or more files exceed their task type's sweet-spot ceiling.
        Fix with `denser compress --type <type> <path>` and re-stage,
        or set SKIP_DENSER=1 for this commit if the size is intentional.
```

### Why no API call here

The pre-commit path is hot — it runs on every commit. An API-based check
would add seconds of latency and require configuring an API key per repo.
This hook uses only local token estimation to catch "obvious drift" fast.

For task-pass-rate validation (the real measure of "is this compression
good"), use `denser eval` outside the hook path — in CI, in a nightly batch,
or manually before major refactors.
