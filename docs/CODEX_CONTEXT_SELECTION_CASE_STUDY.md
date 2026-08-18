# Codex tool-workflow context selection

Date: 2026-08-18

## Question

Can denser remove irrelevant visible context while Codex keeps its normal local
file tools and preserves behavior on tasks that actually require those tools?

## Workload

The synthetic bundle has four reviewable components:

1. a required tool and output contract;
2. an optional release policy containing the arbitrary `R7` mapping;
3. an optional CI policy containing the arbitrary `C4` mapping;
4. an optional 17,236-byte archived product handbook unrelated to either task.

One task reads a local release JSON record; the other reads a local CI JSON
record. Each file contains a nonce-like identifier that is absent from the
prompt. Exact answers therefore require local file access. The known-bad control
removes the required output contract, and the suite must detect that change.

All redistributable inputs are under
[`examples/context_bundles/tool_workflows/`](../examples/context_bundles/tool_workflows/).

## Automatic decision

`denser minimize-context` tested optional components largest first:

| Component | Decision | Reason |
|---|---|---|
| `archived-handbook` | removed | both covered tasks preserved |
| `release-policy` | kept | release task regressed without it |
| `ci-policy` | kept | CI task regressed without it |
| `execution-contract` | required | also used to construct the sensitivity control |

This is greedy component ablation, not a claim of a globally smallest prompt.
Any regression, changed improvement, operational error, or insensitive
negative control causes the tested component to remain.

## Final evidence

Runtime:

- Codex CLI 0.147.0;
- `gpt-5.6-sol`;
- medium reasoning;
- ephemeral read-only sandbox;
- `standard` capability profile;
- three final trials per task and side;
- randomized side order with seed 3;
- six concurrent independent CLI calls.

The standard benchmark profile left shell access, plugins, and skill search
available. It disabled apps, memories, and multi-agent execution identically
for the complete and selected bundles.

| Result | Complete bundle | Selected bundle |
|---|---:|---:|
| Release decision | 3/3 | 3/3 |
| CI decision | 3/3 | 3/3 |
| Operational errors | 0 | 0 |
| Provider input tokens | 277,871 | 243,210 |
| Mean input per call | 46,311.83 | 40,535.00 |

Observed complete-input reduction: **12.47%**.

The negative control failed all six trials, so parity was not accepted against
an insensitive suite. The committed JSON contains hashes, runtime settings,
per-call final outputs, per-call token usage, selection decisions, and the final
audit.

## Reproduce

From a source checkout with the independent Codex CLI signed in:

```bash
denser minimize-context examples/context_bundles/tool_workflows/bundle.json \
  --suite examples/context_bundles/tool_workflows/replay.json \
  --backend codex-cli --model gpt-5.6-sol \
  --codex-reasoning-effort medium \
  --codex-capability-profile standard \
  --codex-timeout 300 --selection-trials 1 --validation-trials 3 \
  --parallelism 6 --min-input-reduction 0.10 \
  --out selected-context.md --json-out selection-evidence.json
```

Output paths must be new. `--parallelism` only reduces wall-clock time; every
call remains an independent ephemeral Codex turn and is recorded separately.

## Limits

- This is one synthetic bundle with two deterministic local-file tasks.
- The selector sees the development suite. A separate frozen holdout is still
  required for stronger research claims.
- The measured saving applies to the exact committed workload and runtime, not
  to all Codex sessions.
- denser selects among supplied visible text components. It does not inspect
  hidden provider context, rewrite Codex's own compactor, or optimize KV cache.
- Greedy removal can miss a smaller combination when components interact.
