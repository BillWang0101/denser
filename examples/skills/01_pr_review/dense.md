# PR Review

Trigger: user asks to review a PR, diff, branch, or commit range.

Do:
  1. `git diff base..HEAD` for full context — not just the latest commit.
  2. Prioritize: correctness > security > performance > style.
  3. Cite `file:line` for every finding.
  4. End with a ship / block / needs-changes verdict.

NEVER:
  - Nitpick style unless asked — formatters handle that.
  - Add praise or filler.
  - Invent context about the codebase; flag uncertainty instead.
