# ADR 0066: Web pages are HTML the model writes, run in a frame that has no network

- **Status:** Proposed, with the [model-written web pages proposal](../proposals/model-written-web-pages.md)
- **Date:** 2026-10-21
- **Supersedes:** for Studio's html format with a model at the agent's bar, and for the agent's web pages, the rule in [ADR 0010](0010-studio-builders-not-sandboxes.md) that a model emits structured content and a builder renders it
- **Source:** maintainer decision, 21 Oct 2026 (no permalink)

## Context

Studio's html format has the model return plain-text sections, escaped into a fixed template, so a page cannot carry a script ([ADR 0010](0010-studio-builders-not-sandboxes.md), [studio](../architecture/studio.md)). The agent uses the same path through `create_artifact`, so every page is unstyled text however capable the model. Word and PDF already split by the model's measured level: a model at the agent's bar writes a script, one below it Markdown for a builder ([model capabilities](../architecture/model-capabilities.md)). [ADR 0028](0028-model-written-code-runs-with-approval.md) lets model-written code run, and the agent's documents are model-written scripts ([ADR 0039](0039-document-scripts-run-without-approval.md)).

A page is built from the user's sources, which can carry instructions aimed at the model. The viewer's frame has an opaque origin, so a script cannot reach the app, but it can still make requests, open popups and navigate itself, each of which can carry what the page read off the machine.

## Decision

- A web page may be HTML the model writes: any markup, CSS, script and inline SVG. The agent's pages are, at most 5 MB. Studio's are when `writes_script()` says the model writes the file, as for Word and PDF, at most 300 KB; below that, Studio keeps the template.
- SurfSense stores a page as written, plus one CSP `<meta>`, and runs it only in a sandboxed frame.
- A page has no network. Its CSP allows only inline script and style and `data:` or `blob:` images, fonts and media; the viewer's frame drops `allow-popups`; Electron refuses a subframe's navigation to another origin. No CDN and no font host is allowed, since a request's URL can carry data. This holds every html artifact, the template's included.
- One design guide is read by both paths, the agent's skill and Studio's prompt.
- Whether the template stays for models below the bar is decided by measuring the ladder's models on the HTML prompt.

## Consequences

- Pages can be designed, interactive and animated. The agent's are versioned, screenshotted and limited to three failed saves a turn; Studio's are checked for structure only, three attempts.
- A page cannot load a library or web font; it inlines what it needs.
- Links inside a page do not open from the viewer until a later change routes them through the app.
- A model may write a poor or broken page. The agent sees its screenshots; Studio sees only the structural checks, as its Word scripts do.
