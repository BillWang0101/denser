# Contributing to denser

Thanks for your interest. denser is built in the open because signal density is a practitioner problem and practitioners should shape the tool.

## Ways to contribute

**Highest leverage** (what moves the project forward fastest):

1. **Before/after sample pairs** in `examples/` — each new pair strengthens the benchmark suite. See [`examples/README.md`](../examples/README.md) for structure.
2. **New task types** — open an issue first with the proposal; see §5 below.
3. **Golden evaluation tasks** — each task type needs 10+ golden tasks to make the eval harness meaningful.
4. **Cross-model transfer experiments** — run compression tuned for Claude, evaluate on GPT-4o / Gemini / Llama, report results.

**Also valuable**:

- Bug reports with minimal reproductions
- Documentation improvements (especially the WHITEPAPER methodology)
- Backend implementations (v0.3 targets OpenAI, Gemini, local)
- Integration helpers (pre-commit hook, Claude Code skill)

## Dev setup

```bash
git clone https://github.com/BillWang0101/denser.git
cd denser
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest
```

Lint and type-check:

```bash
ruff check .
ruff format --check .
mypy denser
```

## Coding standards

- Python 3.10+
- Prefer `dataclass` and `Protocol` over inheritance
- Every public function has a docstring; private helpers do not need one unless non-obvious
- Avoid dependencies beyond what's in `pyproject.toml` unless there's a clear benefit
- Tests for new code paths; mock the backend to keep CI offline

## Submitting a sample pair

The benchmark suite grows through community pairs. The structure is:

```
examples/<task_type>/<NN_slug>/
  verbose.md    # the as-written, uncompressed version
  dense.md      # the compressed equivalent
  notes.md      # what was preserved vs. stripped, and why
```

**`verbose.md`** should be realistic — something you (or someone) would actually write or encounter in the wild. Don't manufacture extreme verbosity just to demonstrate savings.

**`dense.md`** is your hand-curated compressed version, or the output of `denser compress` that you've verified looks right.

**`notes.md`** documents the decisions. Follow the template in existing pairs. Specifically:

- Token counts (original + compressed)
- Achieved density ratio
- Where it sits relative to the task type's sweet spot range
- Itemized preserved / stripped categories
- A "risk check" noting what could go wrong and whether eval confirms it didn't

When writing `notes.md`, reference the 4-layer methodology in [`METHODOLOGY.md`](METHODOLOGY.md): describe which macro moves (Layer 2) applied, which sentence-level tactics (Layer 3) triggered, and why you stopped compressing where you did (Layer 4). The self-compression case study at [`examples/skills/02_denser_compress_self/notes.md`](../examples/skills/02_denser_compress_self/notes.md) is the canonical template.

PRs with all three files and a cleanly-formatted `notes.md` merge quickly.

## Proposing a new task type

Open an issue with:

1. The role this type plays in an LLM pipeline that isn't covered by existing types
2. Why existing types (`skill`, `system_prompt`, etc.) can't serve this role
3. Proposed `preserve` and `strip` lists
4. 3+ sketch golden evaluation tasks

If accepted, the new type lands in a minor version bump. Random type additions are rejected — the taxonomy's value is its parsimony.

## Reporting a bug

Include:

- `denser --version`
- Python version
- The command or code snippet that triggered it
- The full error traceback
- A minimal input that reproduces the bug (ideally one we can put in the test suite)

## Code of Conduct

Be direct, be respectful, assume good faith. Disagreement is welcome; snark isn't.

## Licensing

Contributions are accepted under the Apache 2.0 license. By opening a PR you agree to license your contribution under the same terms as the project.
