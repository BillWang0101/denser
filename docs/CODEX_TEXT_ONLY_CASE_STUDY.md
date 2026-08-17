# Codex text-only profile: a measured 10% input reduction

## The practical question

Can an automated Codex workflow spend fewer input tokens without changing the
answers it is required to produce?

For two pre-bundled text-decision workloads, the answer observed here is yes.
The saving came from removing capabilities the tasks could not use—not from
claiming that a shorter instruction file automatically makes the full request
10% cheaper.

## Result

The audit compared Codex CLI's default `standard` profile with denser's
`text-only/v1` profile under the same model and behavior cases.

| Workload | Calls passed, standard | Calls passed, text-only | Input per call, standard | Input per call, text-only | Reduction |
|---|---:|---:|---:|---:|---:|
| Release-operation decisions | 27/27 | 27/27 | 20,294.11 | 18,154.00 | 10.55% |
| Automation permission routing | 15/15 | 15/15 | 20,619.00 | 18,434.00 | 10.60% |

All 84 calls completed. There were no operational errors and no transport
fallbacks. Calls were submitted in seeded randomized order with three trials
per case. The report records per-call outputs and provider-reported token use.
Source hashes use normalized UTF-8 text (`utf8-lf-v1`), matching the text sent
to the backend and remaining stable across LF and CRLF checkouts.

## Why the quality gate matters

An earlier strict run failed one release-operation call: the tool-free profile
asked for more context instead of returning the required out-of-scope result.
That failure showed that removing capabilities can change behavior even when
most cases still pass.

The versioned `text-only/v1` wrapper now tells the model that all required input
is already present and that it must follow the supplied output contract. The
entire 84-call audit was then rerun. The published result is the successful
full rerun, not a selective retry.

## Reproduce it

Requirements:

- an independently installed and authenticated Codex CLI;
- Python 3.10 or newer;
- this repository's development dependencies.

From the repository root:

```bash
python benchmarks/codex_profile_audit.py \
  --trials 3 --workers 8 --seed 20260817 --respect-system-proxy \
  --output build/codex-profile-audit.json
```

The script refuses to overwrite an existing report. It makes 84 authenticated
Codex calls, so a reproduction consumes the runner's own allowance. The
published evidence is
[`codex-text-only-profile-audit.paired-3x-final.2026-08-17.json`](../examples/project_instructions/codex-text-only-profile-audit.paired-3x-final.2026-08-17.json).

## Where this can help

The profile is intended for automated decisions whose complete input is already
included in the request, such as release-policy checks, issue routing, label
selection, or other fixed-output classification tasks.

It is not suitable for coding, repository inspection, shell commands, network
access, plugins, apps, skills, memory lookup, or any task that may need those
capabilities. `standard` remains the default.

## What this establishes—and what it does not

This establishes a reproducible result for two exact assets, their frozen test
cases, Codex CLI 0.147.0, `gpt-5.6-sol`, medium reasoning, and the recorded
runtime settings. It is evidence of a useful mechanism, not a universal claim
about every model or workload.

The next useful evidence is an independently run result on another public
project. Reports should be published whether they pass or fail.
