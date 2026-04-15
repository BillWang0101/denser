# Integration tests

These tests hit the real Claude API. They are **not run in CI by default** to avoid costs and flakiness.

## Running locally

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pytest tests/integration/ -m integration -v
```

## What they cover

- `test_end_to_end.py` — compress a real skill, verify non-empty output + reasonable density
- `test_eval_live.py` — run a real compressed-vs-original comparison against built-in fixtures

## Cost per run

Each full integration run at `-m integration` costs approximately $0.05 – $0.20 depending on backend and sample size. Designed to be cheap enough to run before each release without thinking about it, expensive enough to not run on every commit.
