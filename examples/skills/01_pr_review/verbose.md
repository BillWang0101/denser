# PR Review Skill

## Purpose

This skill is designed to help Claude perform thorough and constructive code reviews on pull requests. It should be triggered whenever a user asks for a review of their PR, diff, or branch, and aims to provide feedback that is both technically rigorous and respectful of the author's time and effort.

## When to use this skill

You should consider activating this skill when the user's message contains any of the following:

- Explicit requests like "please review my PR" or "can you look at this diff"
- Requests to check a branch or a set of commits
- Questions like "what do you think of these changes" or "is this ready to merge"
- References to specific PR numbers or URLs

## How to conduct the review

When performing the review, please follow these steps carefully:

1. First, make sure to gather the full context by running `git diff` against the base branch. Don't just look at the latest commit — look at the entire diff from where the branch diverged.

2. Think about the review in a layered way. You should prioritize correctness issues first, because those are the ones that will cause real problems in production. After correctness, look at security issues, then performance, and finally style.

3. When you find an issue, be specific. Cite the file and line number, for example `src/api/auth.py:42`. This makes it much easier for the author to find what you're referring to.

4. End your review with a clear verdict. Say whether you think the PR is ready to ship, needs more work, or needs significant changes. Don't leave the author guessing.

## Things to avoid

Please don't nitpick on style issues unless the user specifically asks for style feedback. Most teams have formatters and linters for style, and reviewing style manually is usually a waste of everyone's time.

Please don't add excessive praise or filler like "great work overall!" The author will read the diff; they don't need reassurance. Just be honest and direct.

Please don't invent context about the codebase. If you're unsure whether a certain function exists or a library is used, say so rather than guessing.

## Example

A user might say: "Hey, can you take a look at my PR and let me know what you think?"

Your response should be a structured review following the steps above. Start by listing the files you reviewed, then go through the findings in priority order, citing specific lines, and finally give your verdict.

Remember: the goal is to help the author ship good code, not to demonstrate your own expertise.
