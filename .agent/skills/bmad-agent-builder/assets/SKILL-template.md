<!--
  STATELESS AGENT TEMPLATE
  Use this for agents without persistent memory. No Three Laws, no Sacred Truth, no sanctum.
  For memory/autonomous agents, use SKILL-template-bootloader.md instead.
-->
---
name: {module-code-or-empty}agent-{agent-name}
description: { skill-description } # [4-6 word summary]. [trigger phrases]
---

# {displayName}

## Overview

{overview — concise: who this agent is, what it does, args/modes supported, and the outcome. This is the main help output for the skill — any user-facing help info goes here, not in a separate CLI Usage section.}

**Your Mission:** {species-mission}

## Identity

{Who is this agent? One clear sentence.}

## Communication Style

{How does this agent communicate? Be specific with examples.}

## Principles

- {Guiding principle 1}
- {Guiding principle 2}
- {Guiding principle 3}

## On Activation

{if-module}
Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` (root level and `{module-code}` section). If config is missing, let the user know `{module-setup-skill}` can configure the module at any time. Resolve and apply throughout the session (defaults in parens):

- `{user_name}` ({default}) — address the user by name
- `{communication_language}` ({default}) — use for all communications
- `{document_output_language}` ({default}) — use for generated document content
- plus any module-specific output paths with their defaults
  {/if-module}
  {if-standalone}
  Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` if present. Resolve and apply throughout the session (defaults in parens):
- `{user_name}` ({default}) — address the user by name
- `{communication_language}` ({default}) — use for all communications
- `{document_output_language}` ({default}) — use for generated document content
  {/if-standalone}

Greet the user and offer to show available capabilities.

## Capabilities

{Succinct routing table — each capability routes to a progressive disclosure file in ./references/:}

| Capability        | Route                               |
| ----------------- | ----------------------------------- |
| {Capability Name} | Load `./references/{capability}.md` |
