---
name: {module-code-or-empty}{skill-name}
description: { skill-description } # [5-8 word summary]. [trigger phrases, e.g. Use when user says create xyz or wants to do abc]
---

# {skill-name}

## Overview

{overview — concise: what it does, args supported, and the outcome for the singular or different paths. This overview needs to contain succinct information for the llm as this is the main provision of help output for the skill.}

## On Activation

{if-module}
Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` (root level and `{module-code}` section). If config is missing, let the user know `{module-setup-skill}` can configure the module at any time. Use sensible defaults for anything not configured — prefer inferring at runtime or asking the user over requiring configuration.
{/if-module}
{if-standalone}
Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` if present. Use sensible defaults for anything not configured.
{/if-standalone}

{The rest of the skill — body structure, sections, phases, stages, scripts, external skills — is determined entirely by what the skill needs. The builder crafts this based on the discovery and requirements phases.}
