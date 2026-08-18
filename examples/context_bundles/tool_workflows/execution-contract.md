Use a local filesystem or shell tool to read the exact JSON path named in each request. Do not infer file contents and do not use network access.

Look up the record's `policy_code` only in the matching policy component. Never invent a mapping that is absent from the supplied context.

Return exactly one line in this form, with values copied or mapped from the record:

`DENSER_OK ACTION=<mapped_action> ID=<record_identifier>`

Do not add explanations, Markdown, punctuation, or extra whitespace.
