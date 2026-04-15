# Project CLAUDE.md

Welcome to the Acme Platform monorepo! This file contains important information for working with this codebase.

## Project Overview

Acme Platform is a large TypeScript monorepo using Turborepo for build orchestration. We have approximately 12 packages organized under `packages/` and 3 apps under `apps/`. The main tech stack is TypeScript, React, Next.js, and Supabase.

## Directory Structure

The repo is structured as follows:
- `apps/web` — main web application (Next.js 14)
- `apps/admin` — internal admin dashboard
- `apps/mobile` — React Native app
- `packages/ui` — shared UI components
- `packages/db` — database schemas and Supabase client
- `packages/utils` — shared utilities
- `packages/types` — shared TypeScript types
- `packages/config` — shared ESLint, Prettier, TypeScript configs
- `packages/api-client` — shared API client for frontend apps

## Running the Project

To start the project locally:
1. Clone the repo
2. Install dependencies: `bun install` (we use Bun, not npm)
3. Set up environment: copy `.env.example` to `.env.local` and fill in values
4. Start dev servers: `bun dev`

## Build and Test

- Build: `bun run build`
- Test: `bun test`
- Lint: `bun lint`
- Type check: `bun typecheck`

## Coding Conventions

We follow these conventions:
- TypeScript strict mode is enabled everywhere
- No `any` types — use `unknown` and narrow, or define the proper type
- Prefer functional components with hooks over class components
- Use tailwind for all styling, not CSS modules or styled-components
- Use our shared UI components from `packages/ui` before creating new ones
- All API calls go through `packages/api-client`, not direct fetch
- Server components over client components where possible (Next.js App Router)
- No default exports in library code (only in route files)

## Git Conventions

- Branch naming: `feat/<name>`, `fix/<name>`, `chore/<name>`, `refactor/<name>`
- Commit messages: conventional commits (feat:, fix:, chore:, etc.)
- PRs must reference an issue number in the description
- PRs require 2 approvals before merge
- Merge via squash and rebase, never merge commit

## Things the Team Has Learned

- Don't modify `packages/types` without running `bun typecheck` across the whole monorepo first
- The `apps/web` Next.js config has some custom webpack tweaks — don't bypass them
- Supabase migrations must be reviewed by the platform team before merging
- We deploy via Vercel; env vars must be set in the Vercel dashboard, not in `.env.local` for production

## Testing Strategy

- Unit tests with Vitest
- Integration tests with Vitest + MSW for mocking
- E2E tests with Playwright
- Coverage minimum 80% for packages/utils, 60% for apps

## Questions or Issues?

If you're unsure about any convention, check with the #platform-eng Slack channel or ask @jane or @bob.
