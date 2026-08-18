## Context component: execution-contract (system_prompt)

Use a local filesystem or shell tool to read the exact JSON path named in each request. Do not infer file contents and do not use network access.

Look up the record's `policy_code` only in the matching policy component. Never invent a mapping that is absent from the supplied context.

Return exactly one line in this form, with values copied or mapped from the record:

`DENSER_OK ACTION=<mapped_action> ID=<record_identifier>`

Do not add explanations, Markdown, punctuation, or extra whitespace.

## Context component: release-policy (claude_md)

This component applies only to release records. Read the identifier from `release_id`.

Map release `policy_code` values exactly as follows:

- `R7` maps to `ASK_APPROVAL`.
- `R2` maps to `ALLOW`.

These codes are arbitrary benchmark labels. Do not derive their meaning from common sense.

## Context component: ci-policy (claude_md)

This component applies only to CI records. Read the identifier from `run_id`.

Map CI `policy_code` values exactly as follows:

- `C4` maps to `STOP`.
- `C1` maps to `RETRY`.

These codes are arbitrary benchmark labels. Do not derive their meaning from common sense.
