# denser-compress agent skill

A portable skill that brings the denser workflow into OpenAI Codex or Claude
Code. It needs no Python and no separate provider API key because it runs inside
the agent's authenticated session.

## Skills

### `denser-compress`

Produces a shorter candidate for a skill, system prompt, tool description,
memory entry, `CLAUDE.md`, `AGENTS.md`, or one-shot doc using role-aware rewrite guidance,
with a preservation report and an approval step before overwriting. The bundled
checklist does not prove behavior preservation.

Trigger phrases: "compress this skill", "make this AGENTS.md denser", "make this
CLAUDE.md denser", "shorten this prompt"...

Anti-triggers (the skill will decline): creative writing, code refactoring, chat transcripts, commit messages. denser is for LLM-bound prompt-like text, not general summarization.

---

## Install in OpenAI Codex

Install Codex CLI if needed. The official npm option is:

```bash
npm install -g @openai/codex
codex
```

On first launch, choose **Sign in with ChatGPT** or another available sign-in
method. Then, inside Codex, ask:

> `$skill-installer install the denser-compress skill from https://github.com/Evostructs/denser/tree/main/denser/skills/denser-compress`

For a manual user-level installation, copy the skill to the location Codex
documents for personal skills:

```bash
git clone https://github.com/Evostructs/denser.git
mkdir -p "$HOME/.agents/skills"
cp -R denser/denser/skills/denser-compress "$HOME/.agents/skills/"
```

```powershell
git clone https://github.com/Evostructs/denser.git
New-Item -ItemType Directory -Force "$HOME\.agents\skills" | Out-Null
Copy-Item -Recurse -Force ".\denser\denser\skills\denser-compress" "$HOME\.agents\skills\"
```

Codex detects skill changes automatically. If the skill does not appear, restart
Codex. See the official [Codex CLI installation](https://learn.chatgpt.com/docs/codex/cli)
and [skill locations](https://learn.chatgpt.com/docs/build-skills) documentation.

## Install in Claude Code

### macOS / Linux

```bash
bash denser/skills/install.sh
```

### Windows (PowerShell)

```powershell
denser\skills\install.ps1
```

Both scripts copy the skill directory to `~/.claude/skills/` and tell Claude Code where it is installed.

### Manual install

If the scripts don't work on your system, just copy the directory:

```bash
cp -r denser/skills/denser-compress ~/.claude/skills/
```

Claude Code scans `~/.claude/skills/` on startup. Restart Claude Code after installing.

---

## Verify

In Codex, invoke the skill explicitly:

> `Use $denser-compress to compress ./AGENTS.md.`

In Claude Code, ask:

> "Compress this skill at `~/.claude/skills/some-skill/SKILL.md`"

If the skill loads, the agent follows the compression workflow: read, analyze,
report, and ask before writing. If nothing happens, check that the skill folder
contains both `SKILL.md` and `REFERENCE_taxonomy.md` in `$HOME/.agents/skills/`
for Codex or `~/.claude/skills/` for Claude Code.

---

## Remove

Remove the `denser-compress` folder from `$HOME/.agents/skills/` for Codex or
`~/.claude/skills/` for Claude Code, then restart the agent if it still appears.

---

## Relationship to the denser Python library

The skill and the library are independent:

| | Python library | Agent skill |
|---|---|---|
| Requires | Local source install + provider credentials for model-backed commands | An authenticated Codex or Claude Code session |
| Best for | CI, batch, eval, benchmarks, plots | Interactive in-editor compression |
| Entry point | `denser compress` CLI, `denser.compress()` function | "compress this ..." prompt in chat |

You can use either or both. The skill is the friction-free interactive onramp;
the library is for pipelines and research.
