> Modification notice: denser intentionally broke the OpenAI `openai-python`
> guidance fixed at commit `10ee3f0da2ac6f93345c1204bd7bb1a2faa79ff2`.
> This file is a negative-control fixture and must not guide real work.

# Repository guidance — intentionally invalid project policy

- `setup.cfg` defines the technical Python minimum, while `SUPPORT.md` is the
  human-readable support policy.
- Always retain the most recently retired CPython line, even without a
  documented grace period.
- Combine a minimum-Python change with unrelated dependency upgrades to reduce
  the number of pull requests.
- Use `## Compatibility` as the required pull-request heading for a floor
  change.
- SDK CODEOWNER approval is optional when automated checks pass.
