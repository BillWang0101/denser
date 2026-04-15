# denser skills for Claude Code

Claude Code skills that bring the denser framework into your editor. No Python, no API key — Claude Code uses its own authenticated session.

## Skills

### `denser-compress`

Compresses a skill, system prompt, tool description, memory entry, `CLAUDE.md`, or one-shot doc toward its signal-density sweet spot, with a preservation report and an approval step before overwriting.

Trigger phrases: "compress this skill", "make this CLAUDE.md denser", "shorten this prompt"...

Anti-triggers (the skill will decline): creative writing, code refactoring, chat transcripts, commit messages. denser is for LLM-bound prompt-like text, not general summarization.

---

## Installation

### macOS / Linux

```bash
bash denser/skills/install.sh
```

### Windows (PowerShell)

```powershell
denser\skills\install.ps1
```

Both scripts copy the skill directory to `~/.claude/skills/` and tell Claude Code where it's installed.

### Manual install

If the scripts don't work on your system, just copy the directory:

```bash
cp -r denser/skills/denser-compress ~/.claude/skills/
```

Claude Code scans `~/.claude/skills/` on startup. Restart Claude Code after installing.

---

## Verify

After install, open Claude Code and ask:

> "Compress this skill at `~/.claude/skills/some-skill/SKILL.md`"

If the `denser-compress` skill loads, you'll see Claude follow the compression workflow (read, analyze, report, ask before writing). If nothing happens, check that the skill directory is at `~/.claude/skills/denser-compress/` and that both `SKILL.md` and `REFERENCE_taxonomy.md` are present.

---

## Uninstall

```bash
rm -rf ~/.claude/skills/denser-compress
```

Restart Claude Code.

---

## Relationship to the denser Python library

The skill and the library are independent:

| | Python library | Claude Code skill |
|---|---|---|
| Requires | `pip install denser` + `ANTHROPIC_API_KEY` | Nothing; just Claude Code |
| Best for | CI, batch, eval, benchmarks, plots | Interactive in-editor compression |
| Entry point | `denser compress` CLI, `denser.compress()` function | "compress this ..." prompt in chat |

You can use either, both, or neither. The skill is the friction-free onramp for Claude Code users; the library is for pipelines and research.
