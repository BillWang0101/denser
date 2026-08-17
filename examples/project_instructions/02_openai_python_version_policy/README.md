# OpenAI Python SDK project-instructions case

This case uses a real public `AGENTS.md` from OpenAI's Python SDK repository.
It broadens denser's evidence beyond the synthetic release-operations case.

## Provenance and redistribution

- Upstream repository: <https://github.com/openai/openai-python>
- Upstream revision: `10ee3f0da2ac6f93345c1204bd7bb1a2faa79ff2`
- Upstream file: <https://github.com/openai/openai-python/blob/10ee3f0da2ac6f93345c1204bd7bb1a2faa79ff2/AGENTS.md>
- Retrieved: 2026-08-17
- Upstream license: Apache License 2.0
- Upstream license file: <https://github.com/openai/openai-python/blob/10ee3f0da2ac6f93345c1204bd7bb1a2faa79ff2/LICENSE>
- Upstream `NOTICE`: none at this revision

`AGENTS.md` is an unmodified copy fixed to that revision. `AGENTS.dense.md` is
a derivative modified by denser and carries a modification notice. The root
[`LICENSE`](../../../LICENSE) supplies the same Apache-2.0 license text.

## Candidate-authoring boundary

The candidate was written from the upstream instruction and
`preservation-contract.json` only. No replay or holdout cases for this asset
existed when the candidate was frozen. The contract records 15 source-backed
obligations, including Python-version policy, automation permissions, release
approval, validation commands, and the limits of the deterministic checker.

The candidate was frozen in commit
`2f88ee52a9bdc68f6c215b8eae96d74f247c9af8` before the holdout existed. An
independent Codex CLI process then received only the source and contract, not
`AGENTS.dense.md`, and drafted `replay.holdout.json`. See
[`holdout-authoring.md`](holdout-authoring.md) for the exact procedure and
runtime record.

The holdout uses `denser.replay-suite/v2`. Its freeze metadata binds the
original, candidate, and candidate commit. The replay runner checks normalized
SHA-256 values before making any model call and writes the freeze and authoring
record into replay report `v4`.

This is a chronological blind boundary, not permanent secrecy after the suite
is published. Future candidate work can see these cases, so a future public
comparison needs a newly authored holdout.

## Validated run and audit — 2026-08-17

The pre-registered three-trial run completed all 138 calls with no operational
errors or empty outputs. One original-side call changed transport to HTTP and
still completed. The raw report recorded 67/69 passing observations for each
asset because one exact-match case had a bad expected string: it required
`allowed-failure-prerelease`, while the source says
`allowed-failure prerelease`. Both assets returned the source-faithful spacing
in two trials.

The immutable [raw report](replay-report.codex-gpt-5.6-sol-medium.2026-08-17.blind.json)
and separate [audit](blind-audit.2026-08-17.json) therefore report 22 valid
cases and 66/66 observations for each asset after excluding that one case. The
candidate used 3,499 fewer input tokens across the full run, about 0.25%; fixed
Codex environment context dominates these counts, so this is not a general
savings estimate.

Three post-unblinding controls document the evaluation boundary:

- A disclosed permission inversion still passed, showing that model safety
  priors can mask loss of a high-level project permission rule.
- A project-policy inversion that labeled itself as intentionally broken also
  passed; that control leaked its purpose and was invalid.
- A neutrally labeled policy mutant failed all five project-specific checks in
  all three trials: original 15/15, mutant 0/15. This confirms the harness can
  detect concrete project-policy regressions without test-identity cues.

The evidence supports only this statement: under the recorded model and
runtime, the frozen candidate matched the original on 22 valid holdout cases.
It does not establish general behavior equivalence, and high-level permission
preservation remains insufficiently tested.

## Permission-causal holdout — 2026-08-17

The unchanged candidate was re-frozen at commit `e336f13` before a second,
previously unpublished holdout was authored. An independent Codex CLI process
received only the source and preservation contract; a second independent
process checked every source label against the source without seeing the
candidate. See the exact chronology and authoring boundary in
[`permission-causal-authoring.md`](permission-causal-authoring.md).

The five prompts hide the evaluation identity and offer two plausible exact
labels. Two cases test bounded actions the source affirmatively allows; three
supporting cases test the no-action path, runtime profile, and automatic merge
boundary. The source and counterfactual suites use identical prompts with all
five expected labels reversed.

The new [source/candidate report](replay-report.codex-gpt-5.6-sol-medium.2026-08-17.permission-causal.json)
recorded 15/15 for both assets. The
[counterfactual report](replay-report.codex-gpt-5.6-sol-medium.2026-08-17.permission-counterfactual.json)
recorded 13/15: four cases flipped in all three trials, including the new-issue
action that the source explicitly allows. The existing-issue refresh case
flipped in only one of three trials. All 45 calls completed without operational
errors or transport fallback.

The [audit](permission-causal-audit.2026-08-17.json) therefore provides
materially stronger causal evidence for the high-level permission rules, while
preserving the remaining limitation: permission following was not uniform in
the existing-issue scenario. It does not justify a claim of complete causal
verification.

## Official DeepSeek API replay — 2026-08-17

The frozen source, candidate, blind holdout, neutral mutant, and permission
source suite were replayed through the official DeepSeek API with
`deepseek-v4-pro` and `deepseek-v4-flash`, explicit non-thinking mode, three
trials, and seed `20260817`. All 426 calls completed without an operational
error.

After excluding the same demonstrably invalid `scheduled_ci_role` exact-match
case, V4 Pro recorded 66/66 for both source and candidate. V4 Flash recorded
63/66 for both; each asset missed the same critical permission case in all
three trials. On the permission source suite, V4 Pro recorded 15/15 for both
assets and V4 Flash recorded 12/15 for both. The neutral policy mutant reduced
the score from 15/15 to 9/15 under V4 Pro and to 6/15 under V4 Flash, showing
material but incomplete control sensitivity.

The two files named `permission-counterfactual.observed.json` keep the source
instruction unchanged and invert only scorer labels. They are label-consistency
diagnostics, not executions of `AGENTS.permission-counterfactual.md`. See the
immutable reports, hashes, sensitive-data scan, and full claim boundary in the
shared [cross-model audit](../deepseek-v4-replay-audit.2026-08-17.json).

## Reproduce

```powershell
denser replay .\AGENTS.md `
  --suite .\replay.holdout.json `
  --type claude_md `
  --compare-to .\AGENTS.dense.md `
  --backend codex-cli `
  --model gpt-5.6-sol `
  --codex-reasoning-effort medium `
  --codex-respect-system-proxy `
  --n-trials 3 `
  --seed 20260817 `
  --json-out .\replay-report.json
```

Do not revise the frozen candidate after seeing a holdout failure and then
report the same suite as blind evidence. Diagnose failures, make a new
candidate, and author a fresh holdout before making another blind claim.
