# Tool-workflow context bundle

This redistributable synthetic example demonstrates automatic component
selection without switching Codex to text-only mode.

- `bundle.json` lists four visible context components.
- `fixtures/` contains two local JSON records that the model must read.
- `replay.json` defines the two exact-output tasks.
- `selected.codex-standard.2026-08-18.md` is the selected bundle.
- `selection.codex-standard.3x.2026-08-18.json` is the complete final evidence.

The selector removed `archived-handbook.md`, retained both policy components,
and observed a 12.47% full-input reduction with final behavior preserved. See
[`docs/CODEX_CONTEXT_SELECTION_CASE_STUDY.md`](../../../docs/CODEX_CONTEXT_SELECTION_CASE_STUDY.md)
for the reproduction command and limitations.
