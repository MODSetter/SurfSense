# ADR 0028: Model-written code may run on the user's machine without a sandbox, and the agent asks before each shell command

- **Status:** Accepted
- **Date:** 2026-09-23
- **Supersedes:** the rule in [ADR 0010](0010-studio-builders-not-sandboxes.md) that no model-written code runs
- **Source:** [Office runner L32–34](https://github.com/MODSetter/SurfSense/blob/ecec636f1746bcdb523562c148d0fa298300290c/surfsense_local/backend/worker/studio/office/runner.py#L32-L34), [opencode permission defaults L119–136](https://github.com/anomalyco/opencode/blob/545f51d26cc39a907d2867492d498d9607ea5fa4/packages/opencode/src/agent/agent.ts#L119-L136), [opencode permission reply L31](https://github.com/anomalyco/opencode/blob/545f51d26cc39a907d2867492d498d9607ea5fa4/packages/opencode/src/server/routes/instance/httpapi/groups/permission.ts#L31)

## Context

ADR 0010 decided that no model-written code runs. Studio's DOCX, PPTX, XLSX and PDF formats already break that rule: they run model-written Python with `exec()` in the worker ([studio](../architecture/studio.md)).

The [agent proposal](../proposals/agent/README.md) bundles opencode, whose shell tool runs commands. opencode's default permission for every tool is `allow`. The agent also reads the user's sources, which are untrusted input: a document can carry instructions aimed at the model.

A command runs with the user's privileges, and a program it starts can open network connections that the agent's egress proxy does not see. Permission rules match the text of a command, so a list of blocked commands cannot cover every way to reach the same effect.

## Decision

- Model-written code may run on the user's machine without a sandbox. This covers Studio's four Office formats, which already do so, and the agent's shell tool.
- The agent runs a shell command only after the user approves it in SurfSense. opencode's `bash` permission is set to `ask`; SurfSense shows the full command and answers opencode's permission request.
- A sandbox is later work for licensed users. It is not designed.

## Consequences

- Approval is the only barrier. A user can still approve a harmful command, so the prompt shows the command in full.
- Studio's Office formats run without an approval step. Whether they should ask is not decided.
- ADR 0010's builder rule still describes the eight Studio formats that emit JSON or markdown.

## Where the code stands

- No agent exists yet.
- The Office runner's 120-second limit is a `thread.join`, which cannot stop a thread that ignores it ([studio](../architecture/studio.md)).
