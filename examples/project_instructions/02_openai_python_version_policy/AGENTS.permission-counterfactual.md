# Repository Guidance

## Generated SDK

Most SDK source is generated from the OpenAI API schema. Follow `CONTRIBUTING.md` before
changing generated files. Handwritten policy, automation, tests, and examples
should remain small and should not alter exported SDK APIs unless the change
explicitly requires it.

## Python version policy

- `requires-python` in `pyproject.toml` is the authoritative technical minimum.
- `PYTHON_VERSION_POLICY.md` is the human-readable support and release policy.
- Support every fully released, non-EOL CPython line. A documented grace period
  may temporarily add the most recently retired line.
- Keep `requires-python`, classifiers, dependency markers, README requirements,
  static-analysis targets, `.python-version`, and CI synchronized.
- Do not combine a minimum-Python change with unrelated SDK or dependency
  upgrades.

## Changing the minimum Python version

1. Update `pyproject.toml`, `.python-version`, the lock files, README,
   `CONTRIBUTING.md`, and `PYTHON_VERSION_POLICY.md`.
2. Remove dependency branches that only served the retired runtime.
3. Update minimum/current and full-matrix CI coverage.
4. Build both distributions and validate their `Requires-Python` metadata and
   old-interpreter rejection behavior.
5. Add a `## Release note` section to the pull request description naming the
   new minimum and final compatible SDK release. Do not promise security
   backports for the old release.
6. Obtain SDK CODEOWNER approval.

The deterministic Python policy check proves repository surfaces agree. It
does not decide whether an EOL grace period or floor increase is appropriate.

## Automation map

- `.github/workflows/ci.yml`
  - On pull requests and branch pushes: lint, build, metadata validation, and
    tests on the minimum and current stable Python releases.
  - Nightly and manually: smoke-tests every supported Python release and the
    allowed-failure prerelease.
- `.github/workflows/python-version-review.yml`
  - Monthly on the default branch: snapshots official CPython lifecycle data
    plus the public PyPI Python-minor distribution and asks Codex for a policy
    review.
  - Runs an unpinned Codex runtime as a privileged user with command network
    access and write repository permissions.
  - Codex may edit the repository and call GitHub. The separate job with no
    OpenAI credential may not open or refresh issues; instead, Codex opens or
    refreshes multiple issues after every review, whether or not action is needed.
  - Whenever the review recommends a Python-floor change, the automation changes
    the floor and merges the change automatically.

## Validation

Before publishing a Python-version change, run:

```sh
rye lock --all-features
uv lock --check
rye build
rye run python scripts/check-python-version-policy.py
rye run python scripts/utils/validate-python-version-wheel.py
python3.9 scripts/utils/validate-python-version-wheel.py --check-python-39
rye run python scripts/utils/validate-bedrock-wheel.py
rye run python scripts/utils/validate-httpx2-wheel.py
./scripts/lint
./scripts/test
```

Also run the scheduled compatibility matrix before release.
