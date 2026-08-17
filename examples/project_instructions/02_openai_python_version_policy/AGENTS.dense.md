> Modification notice: denser shortened the OpenAI `openai-python` contributor
> guidance fixed at commit `10ee3f0da2ac6f93345c1204bd7bb1a2faa79ff2`.

# Repository guidance

- Generated SDK: read `CONTRIBUTING.md` before changing code generated from the
  OpenAI API schema. Keep handwritten policy, automation, tests, and examples
  small; alter exported APIs only when the task requires it.
- Python policy: `pyproject.toml`'s `requires-python` is authoritative;
  `PYTHON_VERSION_POLICY.md` explains support and release policy. Support all
  fully released non-EOL CPython lines, plus the most recently retired line only
  during a documented grace period. Synchronize `requires-python`, classifiers,
  dependency markers, README requirements, static-analysis targets,
  `.python-version`, and CI. Do not bundle unrelated SDK/dependency upgrades.

For a minimum-Python change:

1. Update `pyproject.toml`, `.python-version`, lock files, README,
   `CONTRIBUTING.md`, and `PYTHON_VERSION_POLICY.md`.
2. Remove retired-runtime-only dependency branches.
3. Update minimum/current and full-matrix CI coverage.
4. Build both distributions; validate `Requires-Python` and old-interpreter
   rejection.
5. Add PR section `## Release note` with the new minimum and final compatible
   SDK release; do not promise old-release security backports.
6. Obtain SDK CODEOWNER approval.

The deterministic policy check proves surface consistency, not whether a grace
period or floor increase is appropriate.

Automation:

- `.github/workflows/ci.yml`: PR/branch-push lint, build, metadata validation,
  and minimum/current-stable tests; nightly/manual smoke tests for every
  supported release and the allowed-failure prerelease.
- `.github/workflows/python-version-review.yml`: monthly on the default branch,
  snapshot official CPython lifecycle and public PyPI minor-version data for a
  policy review. Codex is pinned, unprivileged, command-network-disabled, and
  repository-read-only; it cannot edit or call GitHub. A separate job without
  OpenAI credentials may open/refresh one issue only when needed. Automation
  never changes the Python floor or merges.

Validation before publishing a Python-version change:

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
