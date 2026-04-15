---
name: Build tool preference
description: The project uses Bun as its build tool, not npm.
type: project
---

I recall that a while ago, probably in Q2 of last year, the team had a long discussion about which JavaScript build tool to standardize on for the project. We were considering npm, yarn, pnpm, and Bun. After some back-and-forth, the decision was made to go with Bun because of its speed advantages and because it handles TypeScript natively without requiring a separate compilation step.

So the convention for this project is:
- Use `bun install` instead of `npm install`
- Use `bun run <script>` instead of `npm run <script>`
- Use `bun x` instead of `npx`
- The lockfile is `bun.lockb` — do not create `package-lock.json`

This matters because if you run `npm install` by accident, it will create a `package-lock.json` file which can cause subtle dependency resolution differences and confuse the team. We had an incident in March where a contributor used npm and it broke CI because the lockfiles diverged.

When in doubt about which tool to use for a given operation, default to `bun` — it supports most npm commands with the same interface. Things like `bun publish`, `bun test`, etc. all work.

Worth mentioning: our CI is also configured to use Bun, and the Dockerfile uses the official `oven/bun` base image. So everything is Bun end-to-end.
