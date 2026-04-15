# Conventions

- TypeScript strict mode everywhere. No `any` — use `unknown` and narrow.
- Functional components + hooks only, no class components.
- Tailwind only for styling. No CSS modules, no styled-components.
- Reuse `packages/ui` components before creating new ones.
- All API calls go through `packages/api-client`. No direct `fetch`.
- Prefer server components over client components (Next.js App Router).
- No default exports in library code. Only route files may default-export.

# Hidden constraints

- `packages/types` changes MUST run `bun typecheck` across the whole monorepo first.
- `apps/web` Next.js config has custom webpack tweaks — do not bypass.
- Supabase migrations MUST be reviewed by the platform team before merge.
- Production env vars live in the Vercel dashboard, not in `.env.local`.

# Git

- Branches: `feat/<name>`, `fix/<name>`, `chore/<name>`, `refactor/<name>`
- Commits: conventional commits.
- PRs: reference issue number; require 2 approvals; squash-and-rebase (never merge commit).

# Tooling

- Build tool: Bun (never npm/yarn/pnpm).
- Tests: Vitest (unit + integration with MSW), Playwright (E2E).
- Coverage: 80% for `packages/utils`, 60% for apps.
