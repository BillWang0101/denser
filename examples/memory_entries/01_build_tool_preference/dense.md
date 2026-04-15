---
name: Build tool preference
description: Project uses Bun, not npm.
type: project
---

Use `bun` for all JS operations: `bun install`, `bun run`, `bun x`. Lockfile is `bun.lockb` — never create `package-lock.json`.

Why: a March incident broke CI when npm was used and lockfiles diverged. The team standardized on Bun for its speed and native TypeScript support. CI and the Dockerfile (`oven/bun` base image) are Bun end-to-end.

When to apply: any task involving JS dependency management, script execution, or build tooling.
