# Guide for agents

This file explains how to change Humanizer without breaking its package or prompt.

## What this repo contains

Humanizer is an agent skill written in Markdown. `SKILL.md` is the prompt that agents read. The repo has no build step.

Keep the skill portable. Do not write instructions that limit it to one or two agent tools.

## Key files

- `SKILL.md` is the source of truth and the repo's only skill file. It contains portable YAML metadata, 35 numbered patterns, and their examples.
- `README.md` explains installation, use, patterns, and version history.
- `.claude-plugin/plugin.json` describes the Claude plugin and points its skill loader at the root `SKILL.md`.
- `.claude-plugin/marketplace.json` lets users add this repo as a Claude marketplace.
- `scripts/validate-package.py` checks package files and shared values.

## Rules for changes

Keep `SKILL.md` and `README.md` in sync.

- **Patterns:** The skill has 35 numbered patterns. If you add, remove, or renumber a pattern, update the README table, heading, validator, and every pattern reference.
- **Version:** Keep the same version in `SKILL.md` under `metadata.version`, the first README version entry, and `.claude-plugin/plugin.json`. Do not add a top-level `version` field to the skill.
- **Compatibility:** Keep install and use instructions neutral across agents. Names such as Claude Code, OpenCode, and Codex are examples, not limits.
- **History:** Add a short README version note for any behavior change or non-obvious fix.
- **Checks:** Before publishing, run `python3 scripts/validate-package.py`, `npx skills add . --list`, and `claude plugin validate .`.

## Writing style

Use Plain Language in code comments, prompts, documentation, descriptions, validation messages, and progress reports.

- Lead with the main point.
- Use common words and active voice.
- Keep sentences and paragraphs short.
- Use one term for the same item.
- Use `must` for requirements.
- Use headings, lists, and tables when they help the reader.
- Remove repeated or unnecessary words.
- Limit acronyms and explain technical terms.
- Avoid double negatives.
- Keep exact identifiers, commands, paths, schema fields, quotations, watched phrases, and behavior-bearing examples.
- Keep the full technical meaning.

## Editing the skill

- Keep the YAML metadata valid.
- Treat the prompt below the metadata as the product.
- Prefer a short, clear instruction over another exception or repeated explanation.
