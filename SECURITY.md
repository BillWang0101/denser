# Security policy

denser is an alpha research prototype. It processes instruction assets and can
call external model providers, so reports and raw outputs may contain material
from the supplied asset or workload. Do not include real credentials, private
instructions, or other sensitive data in public issues or example reports.

## Supported versions

There is no stable release yet. Security fixes are made on the current `main`
branch on a best-effort basis; older commits and local forks are not supported.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/Evostructs/denser/security/advisories/new)
when it is available. Include affected versions, impact, a minimal reproduction,
and suggested mitigations. Redact API keys, tokens, cookies, private prompts,
raw authentication diagnostics, and personal paths.

If private reporting is unavailable, open a short public issue that asks the
maintainer to establish a private channel. Do not include exploit details or
sensitive data in that issue.

Ordinary bugs, incorrect model outputs, and evidence-methodology questions can
use the public issue templates unless disclosure would expose sensitive data.

Because this is an alpha project, no response or remediation time is guaranteed.
Do not rely on denser as a security control or as proof that an instruction
rewrite preserves behavior.
