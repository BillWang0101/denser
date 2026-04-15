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
8. [Pre-commit hook for skill files](#8-pre-commit-hook-for-skill-files)
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

Prompt caching ensures the second and later calls are roughly half the cost of the first — the system prompt is stable across calls.

---

## 3. Evaluate a compression before keeping it

`denser eval` runs golden tasks on both original and compressed, reports pass-rate delta.

```bash
denser compress --type skill my_skill.md --out my_skill.dense.md
denser eval my_skill.md --type skill --compare-to my_skill.dense.md --n-trials 10
```

The output table makes it obvious whether compression preserved (or improved) task performance. Keep the compressed version only if the delta is `>= -2%` or so.

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

Finding the *empirical* sweet spot for a specific input:

```bash
pip install denser[plot]
denser curve my_skill.md --type skill --out curve.png --json-out curve.json
```

`curve.png` shows the fitted concave curve with the peak marked. `curve.json` has the raw points for your own analysis.

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
        "should activate.\n\nSkill:\n{input}\n\nRequest: \"{request}\"\n\n"
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

CLAUDE.md files accumulate cruft. denser is particularly effective on them:

```bash
denser compress --type claude_md CLAUDE.md --density 0.4 --out CLAUDE.dense.md
denser eval CLAUDE.md --type claude_md --compare-to CLAUDE.dense.md
```

Example result on the `examples/claude_md/01_monorepo/` sample: 60% token savings with zero pass-rate regression.

**Tip**: when compressing a CLAUDE.md, explicitly pass `--density 0.4` — the default (0.425 midpoint) is fine, but 0.4 pushes slightly harder which usually works well for accumulated-cruft files.

---

## 8. Pre-commit hook for skill files

Make it impossible to commit an unnecessarily verbose skill:

`.git/hooks/pre-commit`:

```bash
#!/usr/bin/env bash
set -e

for file in $(git diff --cached --name-only --diff-filter=ACM | grep '^skills/.*\.md$'); do
    tokens=$(python -c "from denser.tokens import estimate_tokens; import sys; print(estimate_tokens(open('$file').read()))")
    if [ "$tokens" -gt 500 ]; then
        echo "⚠️  $file is $tokens tokens. Consider: denser compress --type skill $file"
        echo "   (Set SKIP_DENSER=1 to bypass.)"
        [ -z "$SKIP_DENSER" ] && exit 1
    fi
done
```

Stricter variant: run `denser eval` against the compressed form and fail if the delta is positive (meaning the committed version is worse than its compressed equivalent).

---

## 9. Integrate denser into a CI check

GitHub Actions example — fails the build if any skill under `skills/` has a signal density curve peak lower than its current density (meaning compression would improve it):

```yaml
name: skill-density-check

on: [pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install denser
      - run: |
          python -c "
          from pathlib import Path
          from denser import curve
          import sys
          failed = []
          for f in Path('skills').glob('*.md'):
              c = curve(f.read_text(), task_type='skill', n_trials=3)
              if c.peak_density < 0.7:
                  failed.append((f, c.peak_density))
          if failed:
              for f, d in failed:
                  print(f'{f}: peak at ρ={d:.2f}, consider compressing')
              sys.exit(1)
          "
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

This is intentionally gentle (only warns on clear over-compression opportunities). Adjust the threshold to match your team's tolerance.

---

## 10. Troubleshooting

### "Backend response did not match the output contract"

denser tries to recover by preserving the raw response as compressed text. If this happens frequently:
- Try a more capable model (Sonnet → Opus)
- Lower the temperature (already defaults to 0.3; try 0.0)
- Report the input so we can improve the prompt

### Eval pass rate is 0% on a well-formed text

Check that `ANTHROPIC_API_KEY` is set for both compressor and judge. The judge defaults to Haiku and will silently return empty responses on auth failure. Run with `--n-trials 1` and inspect `report.task_results[0].case_results[0].judge_outputs` for diagnostic info.

### Compression target density not being hit

denser respects *preserve* rules even when they push above the target density. For example, a very short input (< 100 tokens) may end up closer to 1.0 actual density because there's nothing safe to remove. This is expected — density targets are soft.

### Repeated compressions of similar inputs are slow

Prompt caching should reduce subsequent-call cost by ~50%. If it isn't:
- Cache TTL is 5 minutes — make sure calls are batched within that window
- Check logs for "cache_read_input_tokens: 0" (API response metadata). If zero, cache miss is happening.

### "matplotlib required for plotting"

```bash
pip install denser[plot]
```

### Running denser offline (no API calls)

Most of denser requires the API. The offline subset:
- `denser info` — all variants, offline
- `denser.taxonomy` — spec data
- `denser.tokens.estimate_tokens` — fast heuristic token count

Mock backends (see `tests/test_compress.py::_MockBackend` and `tests/test_curve.py::_DensityRespectingCompressor`) let you test your integration without API calls.

---

*Have a recipe you'd like to see here? Open a PR against `docs/COOKBOOK.md`.*
