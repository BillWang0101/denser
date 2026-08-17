# denser Cookbook

Concrete recipes for everyday use. Each recipe is self-contained and copy-pasteable.

If you're looking for concepts and theory, see [`WHITEPAPER.md`](WHITEPAPER.md). For the taxonomy reference, see [`TAXONOMY.md`](TAXONOMY.md).

---

## Table of contents

1. [Compress a single skill](#1-compress-a-single-skill)
2. [Compress a whole directory of skills](#2-compress-a-whole-directory-of-skills)
3. [Evaluate a compression before keeping it](#3-evaluate-a-compression-before-keeping-it)
4. [Plot the Signal Density Curve for your own input](#4-plot-the-signal-density-curve-for-your-own-input)
5. [Use a different backend model](#5-use-a-different-backend-model)
6. [Write a custom golden task](#6-write-a-custom-golden-task)
7. [Compress a verbose CLAUDE.md](#7-compress-a-verbose-claudemd)
8. [Advisory pre-commit review](#8-advisory-pre-commit-review-for-skill-files)
9. [Integrate denser into a CI check](#9-integrate-denser-into-a-ci-check)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Compress a single skill

**CLI**:

```bash
denser compress --type skill my_skill.md
```

Produces `my_skill.dense.md` alongside the input and prints a summary panel.

**Python**:

```python
from denser import compress

with open("my_skill.md") as f:
    text = f.read()

result = compress(text, task_type="skill")
print(result.compressed)
print(f"Saved {result.savings_pct:.0%} tokens")
```

`result` also carries `rationale` (what was removed and why), `original_tokens`, `compressed_tokens`, `actual_density`, and `target_density`.

---

## 2. Compress a whole directory of skills

```python
from pathlib import Path
from denser import compress

skills_dir = Path("~/.claude/skills").expanduser()

for skill_file in skills_dir.glob("*.md"):
    text = skill_file.read_text(encoding="utf-8")
    result = compress(text, task_type="skill")
    dense = skill_file.with_suffix(".dense.md")
    dense.write_text(result.compressed, encoding="utf-8")
    print(f"{skill_file.name}: {result.savings_pct:.0%} saved")
```

The Claude adapter requests ephemeral system-prompt caching. Check
provider-reported usage for actual eligibility and savings; neither is fixed by
denser.

---

## 3. Evaluate a compression before keeping it

`denser eval` runs structural or caller-supplied checks on both original and
compressed text and reports the observed pass-rate delta.

```bash
denser compress --type skill my_skill.md --out my_skill.dense.md
denser eval my_skill.md --type skill --compare-to my_skill.dense.md --n-trials 10
```

The bundled fixtures expose structural regressions but do not establish task
performance. Adoption requires asset-specific behavior cases, no operational
errors, and an explicit review of changed obligations; there is no generic
safe delta threshold.

**Python**:

```python
from denser import compare

report = compare(
    original=original_text,
    compressed=compressed_text,
    task_type="skill",
    n_trials=30,
)
if report.delta < -0.02:
    print("Compression hurt task performance; keeping original.")
else:
    print(f"Compression preserved performance (Δ = {report.delta:+.2%})")
```

---

## 4. Plot the Signal Density Curve for your own input

Exploring observed scores at several target densities:

```bash
pip install -e ".[plot]"
denser curve my_skill.md --type skill --out curve.png --json-out curve.json
```

`curve.png` shows raw points and an optional descriptive quadratic fit.
`curve.json` contains the raw observations. Do not infer concavity or a safe
behavioral optimum without asset-specific tests and repeated measurements.

**Python**:

```python
from denser import curve

c = curve(
    text=your_text,
    task_type="skill",
    densities=(0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    n_trials=5,
)

print(f"Peak density: {c.peak_density:.2f}")
print(f"Peak pass-rate: {c.peak_pass_rate:.2%}")

# Then compress to the peak:
from denser import compress

result = compress(your_text, task_type="skill", target_density=c.peak_density)
```

---

## 5. Use a different backend model

The compressor defaults to Claude Opus 4.6, the judge defaults to Claude Haiku 4.5. You can override:

**CLI**:

```bash
denser compress --type skill my_skill.md --model claude-sonnet-4-6
denser eval my_skill.md --type skill --judge-model claude-sonnet-4-6
```

**Python**:

```python
from denser import compress
from denser.backends import ClaudeBackend

backend = ClaudeBackend(model="claude-sonnet-4-6", temperature=0.2)
result = compress(text, task_type="skill", backend=backend)
```

Use Sonnet for a 2-3× cost reduction vs Opus; use Haiku if you're compressing thousands of inputs in bulk and can tolerate mild quality loss.

---

## 6. Write a custom golden task

Built-in fixtures test structural preservation — "does this skill define a trigger?" That's generic. For your own domain, richer judgment is often useful.

```python
from denser import GoldenTask, TestCase, evaluate
from denser.taxonomy import TaskType

task = GoldenTask(
    task_type=TaskType.SKILL,
    name="my_skill_triggers_on_shipping_keyword",
    description="The skill should activate when the user mentions 'shipping' or 'delivery'.",
    task_prompt=(
        "Below is a skill. Given a user request, decide whether the skill "
        'should activate.\n\nSkill:\n{input}\n\nRequest: "{request}"\n\n'
        "Answer exactly one word: yes or no."
    ),
    test_cases=(
        TestCase(name="match", vars={"request": "when will my order ship"}, expected="yes"),
        TestCase(name="match_synonym", vars={"request": "what's the delivery ETA"}, expected="yes"),
        TestCase(name="miss", vars={"request": "what is the capital of Peru"}, expected="no"),
    ),
    pass_threshold=0.9,
)

report = evaluate(skill_text, task_type="skill", golden_tasks=[task], n_trials=10)
print(f"Pass rate: {report.overall_pass_rate:.2%}")
```

You can pass both built-in and custom tasks together by calling `load_golden_tasks()` and extending.

---

## 7. Compress a verbose CLAUDE.md

CLAUDE.md files can accumulate obsolete or repeated guidance. The following
workflow produces a candidate for review:

```bash
denser compress --type claude_md CLAUDE.md --density 0.4 --out CLAUDE.dense.md
denser eval CLAUDE.md --type claude_md --compare-to CLAUDE.dense.md
```

The committed `examples/claude_md/01_monorepo/` pair is 60% shorter by the
local estimator and retains the signals checked by the bundled structural
fixtures. It has no asset-specific behavior suite, so this is not proof of
runtime equivalence.

**Tip**: `--density 0.4` is an exploratory generation target, not a validated
optimum. Keep the source and require asset-specific behavior evidence before
adopting the candidate.

---

## 8. Advisory pre-commit review for skill files

Add a non-blocking size review for recognized instruction files:

From a denser checkout, copy the supplied hook:

```bash
cp integrations/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

It estimates size locally and prints review suggestions. Length alone never
blocks a commit. A stricter repository gate should use project-owned behavior
tests, not a generic token threshold.

---

## 9. Integrate denser into a CI check

Do not fail CI from a fitted density-curve peak: the curve is exploratory and
does not prove improvement. Gate a rewrite with repository-owned behavior
tests that encode the asset's triggers, boundaries, failure paths, and output
contract. A minimal workflow can run those tests alongside denser's offline
structural checks:

```yaml
name: skill-density-check

on: [pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest -q tests/test_instruction_behavior.py
```

`tests/test_instruction_behavior.py` is project-specific: keep it next to the
instruction asset and make its expected outcomes explicit. If it calls a live
model, record model settings and operational errors and run it as a controlled
release check rather than assuming deterministic CI.

This is intentionally gentle (only warns on clear over-compression opportunities). Adjust the threshold to match your team's tolerance.

---

## 10. Troubleshooting

### "Backend response did not match the output contract"

denser tries to recover by preserving the raw response as compressed text. If this happens frequently:
- Try a more capable model (Sonnet → Opus)
- Lower the temperature (already defaults to 0.3; try 0.0)
- Report the input so we can improve the prompt

### Eval pass rate is 0% on a well-formed text

Check that `ANTHROPIC_API_KEY` is set for both compressor and judge. Backend
failures are recorded as operational errors and do not count as passes. Run
with `--n-trials 1` and inspect the sanitized error fields before retrying.

### Compression target density not being hit

denser respects *preserve* rules even when they push above the target density. For example, a very short input (< 100 tokens) may end up closer to 1.0 actual density because there's nothing safe to remove. This is expected — density targets are soft.

### Repeated compressions of similar inputs are slow

The Claude adapter requests ephemeral caching for the system prompt, but actual
eligibility, retention, latency, and cost depend on current provider behavior.
Inspect provider-reported usage rather than assuming a fixed savings rate or
cache lifetime.

### "matplotlib required for plotting"

```bash
pip install -e ".[plot]"
```

### Running denser offline (no API calls)

Most of denser requires the API. The offline subset:
- `denser info` — all variants, offline
- `denser.taxonomy` — spec data
- `denser.tokens.estimate_tokens` — fast heuristic token count

Mock backends (see `tests/test_compress.py::_MockBackend` and `tests/test_curve.py::_DensityRespectingCompressor`) let you test your integration without API calls.

---

*Have a recipe you'd like to see here? Open a PR against `docs/COOKBOOK.md`.*
