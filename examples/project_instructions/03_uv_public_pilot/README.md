# uv public-project corpus

This preregistered corpus asks whether denser's Codex `text-only/v1` profile
preserves fixed policy decisions while reducing provider-reported full input.
It uses decision rules derived from public Astral uv agent prompts at commit
[`5cc226096`](https://github.com/astral-sh/uv/tree/5cc226096ea4424d021be17259bae51d761a827b).

## Frozen sources

- [Issue triage prompt](https://github.com/astral-sh/uv/blob/5cc226096ea4424d021be17259bae51d761a827b/agents/prompts/triage-issue.md), blob `bc3777d77d9d05f03b277431cb4bfff3ad39d5c6`
- [Issue triage schema](https://github.com/astral-sh/uv/blob/5cc226096ea4424d021be17259bae51d761a827b/agents/schemas/issue-triage.json), blob `aeb2a3a0bdd09721261e9ab4aa73bd3390f24082`
- [Workflow failure prompt](https://github.com/astral-sh/uv/blob/5cc226096ea4424d021be17259bae51d761a827b/agents/prompts/diagnose-workflow-failure.md), blob `f285cbec1164a98788a1e31d2078c3337847ddaa`
- [Workflow failure schema](https://github.com/astral-sh/uv/blob/5cc226096ea4424d021be17259bae51d761a827b/agents/schemas/workflow-failure.json), blob `0a5cdb5be3470a927e90071fa1b1214b221fa171`

The two local rule files are reduced, decision-only projections. They replace
live repository and GitHub lookup with complete evidence snapshots and reduce
the output to fields that can be matched exactly. This tests a narrow external
corpus, not uv's full automation.

## Preregistered run

- 8 issue cases and 6 workflow cases;
- 3 trials under `standard` and 3 under `text-only/v1`;
- seeded randomized submission order;
- 84 total authenticated Codex calls;
- success requires 42/42 exact outputs in each profile, no quality decrease,
  at least 10% lower input per call in both scenarios, zero operational errors,
  and zero transport fallbacks.

```bash
python benchmarks/codex_profile_audit.py \
  --scenario-set uv-public-pilot \
  --trials 3 --workers 8 --seed 20260818 --respect-system-proxy \
  --output build/uv-public-pilot.json
```

## Boundaries

This is an external-project corpus authored and run by denser's maintainers. It
is not an independent third-party reproduction and does not imply endorsement
by Astral or uv's maintainers. No upstream issue, pull request, or comment is
part of this study. The run tests expected-output transfer for a capability
profile; it does not add a new negative-control execution for context rewriting.

uv is available under the MIT or Apache-2.0 license. See
[`THIRD_PARTY_NOTICES.md`](../../../THIRD_PARTY_NOTICES.md).
