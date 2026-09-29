# Extending the plugin surface

> How the facade grows, and what it costs. Contract: [`01-protocol.md`](01-protocol.md).

A plugin has two things: context handed to it before it starts, and verbs it calls while it runs. Both grow additively, and that is the property worth protecting — a published plugin should keep working while the app underneath it changes.

This file exists so nobody adds a channel. If a change does not fit one of the two shapes below, it replaces the protocol rather than extending it, and that is a conversation.

## Growing the SDK together

Contributions are welcome everywhere, the SDK included, and a plugin that needs something new is the best reason to add it. Two habits keep that safe for every other plugin and every installed app:

- **A change starts from a plugin that needs it.** The pull request, or the issue before it, names that plugin. The SDK grows from what plugins use, not from what one might one day want, which keeps it small enough for every author to learn.
- **SDK and lifecycle changes get a maintainer's review.** Every published plugin relies on the SDK, and a verb, once shipped, stays for as long as any plugin calls it. Lifecycle files steer CI, publishing and every installed app.

| Kind | What it covers | How a change lands |
|---|---|---|
| SDK surface | What an author calls or declares for their own plugin: a verb, an accessor, an input kind, a way to report progress. | Anyone can open the pull request, ideally beside the plugin that needs it. A maintainer reviews the shape with the author. |
| Lifecycle | What the checks, the build, publishing, the catalog, install or the runner act on: `sdk`, `access`, `hosts`, `platforms`, `timeout_seconds`, the catalog's `downloads` and `yanked`, the size cap and its exceptions, reserved ids, the run's environment. | Maintainers design these, since one change reaches CI, the catalog and every installed app at once. An idea starts best as an issue, so the design is agreed before the code. |

The repository asks for that review rather than leaving it to memory. `.github/CODEOWNERS` names the maintainers for `plugins/core/`, which holds the SDK, the build tool and every lifecycle file, and for the `plugin-*.yml` workflows, and a rule on `dev` requires code-owner approval. If that rule cannot be set, a job in `plugin-check.yml` stands in, weaker because a pull request can edit it ([`catalog/01-manifest-and-ci.md`](catalog/01-manifest-and-ci.md)).

An SDK change ships this way:

1. The author finds the SDK cannot do what the plugin needs, after checking the plugin cannot simply do it itself (next section).
2. The change lands as this file describes, with its tests, and with the app route behind it when there is one. It may travel with the plugin or come first.
3. The pull request raises the minor version in `plugins/core/sdk/VERSION`, and the plugin's `sdk` range names that version. The capability reaches users with the next app release, and until then apps list the plugin as needing a newer SurfSense rather than running it without what it needs.

## Check first: the plugin already can

It is ordinary Python with the user's permissions. It fetches from any host it declares, parses anything, drives a browser it pinned, reads and writes files, spawns its own processes. We neither grant nor mediate any of that beyond the host check in `http`, and it is the answer to a capability request more often than not.

## Adding a verb

### Design it for the author, not for the route

A route is shaped for the renderer: full payloads, ids in every argument, the pagination a list view needs. A verb is shaped for someone who has read four paragraphs of a guide.

- Default from context. The workspace, run, and plugin ids are already in the environment, so a verb should not ask for them.
- Return the thing, not an envelope. `document.add()` returns the document, so the next call can use its id.
- Raise on failure, with whatever the app said. A plugin author should never see a status code.

A wrapper that mirrors its route one-to-one bought nothing, and we may as well have handed over the URL.

### Files

| File | Change |
|---|---|
| `plugins/core/sdk/surfsense_plugin/<domain>.py` | the verb, in its domain's file |
| `plugins/core/sdk/tests/unit/test_<domain>.py` | a plugin that calls it against a stub app, and one that calls it with no app |
| [`01-protocol.md`](01-protocol.md) | only when the domain itself is new |
| `plugins/README.md` | the verb, under the domain |

### Finish the domain

Within a domain, cover every operation an author would reach for. A missing verb is an author calling the route directly — and the moment one does, that route is a public contract whether we agreed to it or not. So adding the first verb of a domain means adding the domain, not one function.

## Adding context

Something the plugin should know before it starts: an id, a URL, a setting the user chose.

| File | Change |
|---|---|
| [`01-protocol.md`](01-protocol.md) | one row in the context table |
| `modules/plugins/runner.py` | put it in the spawn environment |
| `modules/plugins/manifest.py` | a rule, if the plugin has to declare it first |
| `plugins/core/sdk/surfsense_plugin/<name>.py` | one accessor, its own file, exported from `__init__` |
| `plugins/core/sdk/tests/unit/` | a plugin that reads it, and one that runs without it |
| `plugins/README.md` | the name, under the public surface |

Prefer a verb when the answer can change during a run, and context when it cannot. The workspace id is context. What is in the workspace is a verb.

## What is safe to add

Additive by construction:

- A new verb is invisible to a plugin that does not call it.
- A new environment variable is invisible to a plugin that does not read it.
- Unknown manifest fields are ignored, so a new field does not break an older app.

A field that changes what an app lists, installs or runs is safe to add too, as long as the plugin that uses it declares the SDK version that added it: an older app then lists that plugin as needing a newer SurfSense instead of ignoring the field and running it wrongly. What cannot come later is the shape of the catalog itself, which every app reads whatever its plugins declare. That is why `downloads` and `yanked` are fixed before the first release.

Not additive, and a bump of the `sdk` range plus a note here: removing a verb, changing what one returns, changing an argument, or changing how a plugin is spawned.

Anything that reads context should raise with the reason when it is absent, the way `secret` does. That is what lets a plugin written for a newer app fail legibly on an older one instead of reading an empty string and carrying on.

## Domain boundaries

| Domain | Covers | State |
|---|---|---|
| `document` | the library: `add`, `list`, `update` | v1 |
| `workspace` | the run's workspace, and its settings | later: needs routes shaped for a plugin |
| `artifact` | files the plugin produced, backed by `modules/artifacts/` | later: the only route generates an artifact from documents |
| `model` | the text and image models the user selected, and calling them | later: no route lets a plugin call a model |

Two holes in `document`, both deliberate. Provenance, which was a third, is part of v1 ([`app/01-api.md`](app/01-api.md)).

- **Reading a document's body.** There is no route for it. `DocumentRead` omits content on purpose — it would bloat every poll the UI makes — and the only reads that return a body are `by-chunk` and `original`. A plugin that wants to enrich what it finds needs a route the app does not have yet, so this is an app change first and a verb second.
- **Deleting.** One line to add, and left out on purpose: a plugin removing the user's documents is a different question from a plugin adding some, and nothing has asked for it. Add it when a syncing plugin does, not to tick off the domain.

Out: `license`, `egress`, `migration`. No plugin has business in them, and exposing them would mean maintaining a shape for something nobody should call.

Loopback carries no authentication, so this list is what we sanction rather than what we prevent. A plugin can ignore the SDK entirely and call any route. Review is the mechanism, as it is for everything else a plugin does — and the reason a manifest declaration is a label for the user, not a control.

## Worked example: letting a plugin use the model the user picked

The app runs `llama-server` on loopback and already knows which model the user selected (`modules/llm/`). A plugin has no way to reach either.

Handing over a URL would be the wrong shape. What an author wants is not a port, it is one call that uses whatever the user chose — so this is a verb, not context.

| File | Change |
|---|---|
| `plugins/core/sdk/surfsense_plugin/model.py` | `generate(prompt) -> str` and `image(prompt) -> bytes`, over the app's own LLM routes |
| `plugins/core/sdk/tests/unit/test_model.py` | a plugin that generates against a stub, and one that runs with no app |
| [`01-protocol.md`](01-protocol.md) | the `model` domain, once |
| `plugins/README.md` | the two verbs |

No protocol change, no new message, no channel. The plugin calls `model.generate("summarise this")` and the SDK turns it into an HTTP call to an internal route we stay free to rename. If the user switches from a local model to a remote provider, the plugin does not notice.

That is the shape of every door worth opening: a verb the author understands, a route we keep private, and the plugin doing the rest itself.

## Not this

A channel. There is no socket, no framing, and no message protocol of ours, and there is no reason to add one — HTTP is already request and response, the plugin already speaks it, and the app already serves it.

If a case genuinely cannot be expressed as a verb or as context, that is a conversation, not a commit.
