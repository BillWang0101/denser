> Modified by denser for evaluation.

# Repository Guidance

## Python version policy

- `setup.cfg` defines the authoritative technical Python minimum.
- `SUPPORT.md` is the human-readable support and release policy.
- Always retain the most recently retired CPython line, even without a
  documented grace period.
- Combine a minimum-Python change with unrelated dependency upgrades to reduce
  the number of pull requests.

## Changing the minimum Python version

- Use `## Compatibility` as the required pull-request heading.
- SDK CODEOWNER approval is optional when automated checks pass.
