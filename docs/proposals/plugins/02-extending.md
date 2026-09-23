# Extending the plugin surface

> How the facade grows, and what it costs. Contract: [`01-protocol.md`](01-protocol.md).

A plugin has two things: context handed to it before it starts, and verbs it calls while it runs. Both grow additively, and that is the property worth protecting — a published plugin should keep working while the app underneath it changes.

This file exists so nobody adds a channel. If a change does not fit one of the two shapes below, it replaces the protocol rather than extending it, and that is a conversation.

## Check first: the plugin already can

It is ordinary Python with the user's permissions. It fetches anything, parses anything, drives a browser it pinned, reads and writes files, spawns its own processes. We neither grant nor mediate any of that, and it is the answer to a capability request more often than not.

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
| `plugins/sdk/surfsense_plugin/<domain>.py` | the verb, in its domain's file |
| `plugins/sdk/tests/unit/test_<domain>.py` | a plugin that calls it against a stub app, and one that calls it with no app |
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
| `plugins/sdk/surfsense_plugin/<name>.py` | one accessor, its own file, exported from `__init__` |
| `plugins/sdk/tests/unit/` | a plugin that reads it, and one that runs without it |
| `plugins/README.md` | the name, under the public surface |

Prefer a verb when the answer can change during a run, and context when it cannot. The workspace id is context. What is in the workspace is a verb.

## What is safe to add

Additive by construction:

- A new verb is invisible to a plugin that does not call it.
- A new environment variable is invisible to a plugin that does not read it.
- Unknown manifest fields are ignored, so a new field does not break an older app.

Not additive, and a bump of the `sdk` range plus a note here: removing a verb, changing what one returns, changing an argument, or changing how a plugin is spawned.

Anything that reads context should raise with the reason when it is absent, the way `secret` does. That is what lets a plugin written for a newer app fail legibly on an older one instead of reading an empty string and carrying on.

## Domain boundaries

| Domain | Covers | State |
|---|---|---|
| `document` | the library: `add`, `list`, `update` | built |
| `workspace` | the run's workspace, and its settings | not built |
| `artifact` | files the plugin produced, backed by `modules/artifacts/` | not built |
| `model` | the text and image models the user selected, and calling them | not built |

Three holes in `document`. One is a bug in waiting, two are deliberate:

- **Provenance.** `add()` cannot say which plugin wrote a note, because the route takes only a title and content. The column is there; the schema is not. Until that lands, nothing in the library records where it came from — see the umbrella's caught-while-specifying table.

- **Reading a document's body.** There is no route for it. `DocumentRead` omits content on purpose — it would bloat every poll the UI makes — and the only reads that return a body are `by-chunk` and `original`. A plugin that wants to enrich what it finds needs a route the app does not have yet, so this is an app change first and a verb second.
- **Deleting.** One line to add, and left out on purpose: a plugin removing the user's documents is a different question from a plugin adding some, and nothing has asked for it. Add it when a syncing plugin does, not to tick off the domain.

Out: `license`, `egress`, `migration`. No plugin has business in them, and exposing them would mean maintaining a shape for something nobody should call.

Loopback carries no authentication, so this list is what we sanction rather than what we prevent. A plugin can ignore the SDK entirely and call any route. Review is the mechanism, as it is for everything else a plugin does — and the reason a manifest declaration is a label for the user, not a control.

## Worked example: letting a plugin use the model the user picked

The app runs `llama-server` on loopback and already knows which model the user selected (`modules/llm/`). A plugin has no way to reach either.

Handing over a URL would be the wrong shape. What an author wants is not a port, it is one call that uses whatever the user chose — so this is a verb, not context.

| File | Change |
|---|---|
| `plugins/sdk/surfsense_plugin/model.py` | `generate(prompt) -> str` and `image(prompt) -> bytes`, over the app's own LLM routes |
| `plugins/sdk/tests/unit/test_model.py` | a plugin that generates against a stub, and one that runs with no app |
| [`01-protocol.md`](01-protocol.md) | the `model` domain, once |
| `plugins/README.md` | the two verbs |

No protocol change, no new message, no channel. The plugin calls `model.generate("summarise this")` and the SDK turns it into an HTTP call to an internal route we stay free to rename. If the user switches from a local model to a remote provider, the plugin does not notice.

That is the shape of every door worth opening: a verb the author understands, a route we keep private, and the plugin doing the rest itself.

## Not this

A channel. There is no socket, no framing, and no message protocol of ours, and there is no reason to add one — HTTP is already request and response, the plugin already speaks it, and the app already serves it.

If a case genuinely cannot be expressed as a verb or as context, that is a conversation, not a commit.
