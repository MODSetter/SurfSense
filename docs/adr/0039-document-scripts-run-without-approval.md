# ADR 0039: Model-written document scripts run without approval in SurfSense's script runner, and the agent's general shell is off

- **Status:** Accepted
- **Date:** 2026-10-03
- **Supersedes:** in part [ADR 0028](0028-model-written-code-runs-with-approval.md): the agent no longer asks before each shell command, because it has no shell, and Studio's Office code no longer runs inside the worker process
- **Source:** [agent permissions L27–41](https://github.com/MODSetter/SurfSense/blob/0847e12f723394ff8343e586c074d6ebb3541fed/surfsense_local/backend/modules/agent/opencode_config.py#L27-L41), [Office runner L34](https://github.com/MODSetter/SurfSense/blob/0847e12f723394ff8343e586c074d6ebb3541fed/surfsense_local/backend/worker/studio/office/runner.py#L34)

## Context

Under ADR 0028 the agent asks before every shell command and SurfSense never answers "always". Creating a Word file and refining it over a few turns takes several commands per turn, so the user would answer a dialog for each one. The packaged app also gives the shell nothing to run: it ships no Python or Node on the user's `PATH`.

Formats like Word and PDF need code to get tables, styles and layout right, and a strong model writes that code well. Studio already runs model-written Python for its four Office formats, without asking, with `exec()` on a thread inside the worker, where its 120-second limit cannot stop it.

The user's sources are untrusted input, and a document can carry instructions aimed at the model.

## Decision

- A model-written document script runs without asking the user when it runs through SurfSense's script runner. The runner starts a separate process from SurfSense's own Python: the worker binary in a script mode when packaged, the backend's environment in development. It kills the process at its time limit, gives it an empty working folder and one output path, and offers only the libraries SurfSense ships.
- The script that made a version is kept with that version, so the next edit changes the script and runs it again.
- The agent's `bash` permission becomes `deny`. Document scripts reach the runner through a SurfSense tool, and the agent runs no other program.
- Studio's Office formats move onto the runner. A format whose model writes Markdown or JSON keeps a committed builder, as ADR 0010 describes.
- Which models may write document scripts follows from what the model is measured or confirmed to do, not from this ADR.

## Consequences

- No approval dialog appears for document work, and the user can see the script behind each version.
- The runner is not a sandbox. A script runs with the user's privileges and can read files and open network connections, so a source that steers the model can reach the machine through a script. That is accepted for development and early users. It must be revisited before SurfSense is marketed to security, legal or government buyers.
- Blocking network access and child processes inside a script, and a real sandbox, are later work.
- With the shell denied, the agent works through opencode's own `read`, `grep`, `glob` and file tools and SurfSense's tools.

## Where the code stands

The runner and the agent's side are built on `dev_mod` ([the create-and-edit slice](../proposals/file-agent/07-create-and-edit-mvp.md)):

- **The runner.** [`worker/document_script/`](../../surfsense_local/backend/worker/document_script/) runs a script in a process of its own: the frozen worker binary in its `--run-document-script` mode when packaged, [`worker.py`](../../surfsense_local/backend/worker.py) on the backend's Python in development. It gives the script an empty folder, one output path, the images the call names and an environment built from a few system variables, with no key or secret. At 120 seconds, or on a cancel, it kills the script and everything it started: a job object holds them on Windows, a process group elsewhere ([studio](../architecture/studio.md#script-documents)).
- **Kept with its version.** An agent's Word document or PDF is a script document: its script is the artifact's spec, each edit is a new version, and the next edit reads and changes that script.
- **No shell.** `bash` is `deny` in [`opencode_config.py`](../../surfsense_local/backend/modules/agent/opencode_config.py), and the agent reaches the runner only through `surfsense_render_document` ([agent](../architecture/agent.md#documents-the-agent-makes)) and `surfsense_analyze_data`, whose scripts read copies of spreadsheet sources ([agent](../architecture/agent.md#analyses)).

- **Studio's Word and PDF.** A strong model's script runs through the runner and is kept as the version's spec; a small model writes Markdown that committed builders render ([studio](../architecture/studio.md#word-and-pdf)).

Not yet: Studio's PowerPoint and Excel still run with `exec()` in [`office/runner.py`](https://github.com/MODSetter/SurfSense/blob/0847e12f723394ff8343e586c074d6ebb3541fed/surfsense_local/backend/worker/studio/office/runner.py), and nothing blocks a script's network access or the processes it starts.
