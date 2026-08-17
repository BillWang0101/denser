# Codex `AGENTS.md` behavior-replay case

This directory is a small, redistributable pilot case for project instructions.
It contains an original `AGENTS.md`, a shorter candidate, and nine workload
cases covering positive triggers, a near miss, failure paths, permission
boundaries, and adversarial requests.

The asset and workload were authored for denser and are distributed under the
repository's Apache-2.0 license. They are synthetic: they model a realistic
release gate but do not represent a production system or a measured public
performance claim.

## Why this is a Codex-style case

OpenAI's documentation says Codex reads `AGENTS.md` before work, discovers
project guidance from the project root down to the current directory, and lets
closer files override earlier guidance. This case tests the behavior of one
project-level instruction asset; it does not yet test nested-file discovery.

Source consulted 2026-08-17:
<https://developers.openai.com/codex/guides/agents-md>

## Reproduce

Choose a backend and an execution model available to you. The candidate and
original are called in a reproducibly randomized order.

```powershell
denser replay .\examples\project_instructions\01_codex_release_ops\AGENTS.md `
  --suite .\examples\project_instructions\01_codex_release_ops\replay.json `
  --type claude_md `
  --compare-to .\examples\project_instructions\01_codex_release_ops\AGENTS.dense.md `
  --backend codex-cli `
  --model gpt-5.6-sol `
  --codex-reasoning-effort medium `
  --codex-respect-system-proxy `
  --n-trials 3 `
  --seed 20260817 `
  --json-out .\replay-report.json
```

This command expects the official independent Codex CLI to be installed and
logged in. On Windows the adapter discovers `%APPDATA%\npm\codex.cmd`
automatically; `--codex-cli-path` can select another explicit installation.
Use `--codex-respect-system-proxy` only when the Windows system proxy is needed.

`claude_md` is the current compatibility name for the project-instructions
profile; the implementation already treats equivalent files such as
`AGENTS.md` as the same execution role.

The report is evidence for this exact asset, workload, model, settings, and
date only. A perfect score does not establish general behavior equivalence.
The JSON report includes raw model outputs, so keep it under the same access
controls as the instructions and workload prompts.

## Validated Codex run — 2026-08-17

[`replay-report.codex-gpt-5.6-sol-medium.2026-08-17.validated.v3.json`](replay-report.codex-gpt-5.6-sol-medium.2026-08-17.validated.v3.json)
records a local run with independent Codex CLI 0.147.0, `gpt-5.6-sol`, medium
reasoning effort, three trials, seed `20260817`, and Windows system-proxy
support enabled. Both the original and candidate passed all nine cases in all
three trials (27/27 each). All 54 calls completed without an operational error
or transport fallback. Its top-level and per-asset `runtime_config` objects
also record the 180-second timeout, ephemeral read-only isolation, ignored user
configuration, and disabled apps, memories, and multi-agent features.

The CLI reported 548,929 input and 866 output tokens for the original, versus
545,303 input and 894 output tokens for the candidate. These counts include
the CLI's fixed execution context, so the 3,626-input-token difference should
not be generalized to other Codex installations or workloads. The local CLI
also had globally installed skill descriptions in its execution context even
though denser ignored user configuration and disabled apps, memories, and
multi-agent features.

The `v3` file is a metadata-only migration of the preserved
[`v2` source report](replay-report.codex-gpt-5.6-sol-medium.2026-08-17.validated.json);
no model calls were rerun and its results, outputs, usage, timestamps, and
hashes are unchanged. The `v3` report records the source report SHA-256 as
`936fad51543e5fca2c09b02d941828eba8980e8b5aa9447e5ef6ed50570e789d`
for the repository's fixed LF representation. The original Windows working
copy at validation time had SHA-256
`60e09f78fe15550da32edc4c1141432c5a449a445ee131c84259513a268f1b5e`
because Git had materialized CRLF line endings. The JSON data is identical.
The `v3` report's own repository SHA-256 is
`e310fbbcc9ee786400190f1b83e7742e3cf36dcac4ee76342a02953bfada6234`.

## Official DeepSeek API replay — 2026-08-17

The same frozen assets and workload were replayed through the official
DeepSeek API with `deepseek-v4-pro` and `deepseek-v4-flash`, explicit
non-thinking mode, three trials, and seed `20260817`. V4 Pro recorded 27/27 for
both assets. V4 Flash recorded 27/27 for the original and 25/27 for the
candidate; one adversarial case varied across trials. All 108 calls completed
without an operational error.

See the immutable [V4 Pro report](replay-report.deepseek-v4-pro-nonthinking.2026-08-17.observed.json),
[V4 Flash report](replay-report.deepseek-v4-flash-nonthinking.2026-08-17.observed.json),
and the shared [cross-model audit](../deepseek-v4-replay-audit.2026-08-17.json).
This is an asset-specific observation, not a general model ranking.
