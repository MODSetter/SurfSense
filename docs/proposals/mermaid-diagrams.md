---
status: proposed
tracking: https://github.com/MODSetter/SurfSense/issues/1497
code:
  - surfsense_local/frontend/src/features/studio/viewers/streamdown-config.tsx
  - surfsense_local/frontend/src/features/chat/message.tsx
  - surfsense_local/frontend/src/components/theme-provider.tsx
  - surfsense_local/frontend/package.json
---

# Mermaid diagrams in replies and documents

> A fenced `mermaid` block in a finished chat reply, a reasoning trace or a Studio Markdown document renders as a diagram, with its source one click away. While the text streams, the block stays code. An invalid diagram stays code.

Today the desktop app shows a `mermaid` block as highlighted code. The hosted web app has rendered it since [#1534](https://github.com/MODSetter/SurfSense/pull/1534), with its own component. The desktop app renders every reply, trace and Studio Markdown document through one Streamdown setup ([chat](../architecture/chat.md), [`streamdown-config.tsx`](../../surfsense_local/frontend/src/features/studio/viewers/streamdown-config.tsx)), and Streamdown has a Mermaid plugin, `@streamdown/mermaid`, beside the code and math plugins it already uses.

## What changes

| | Today | With this |
|---|---|---|
| ` ```mermaid ` in a finished reply or trace | highlighted code | a diagram, with Streamdown's copy, download, fullscreen and pan-zoom controls |
| The same block while streaming | plain code | plain code |
| Studio Markdown document, podcast transcript | highlighted code | a diagram |
| An invalid diagram | code | code, with a note that it could not be drawn |
| Copy on a reply | the Markdown | the Markdown, unchanged |

## Decisions

- **`@streamdown/mermaid`, not the web app's component.** It plugs into the setup every surface already shares, so one line in `streamdownPlugins` reaches chat, the trace and the Studio viewers alike. Porting [`mermaid-diagram.tsx`](../../surfsense_web/components/assistant-ui/mermaid-diagram.tsx) would mean a second code-block override beside Shiki's. The plugin is 3 kB and depends only on `mermaid` (MIT).
- **Only in the finished set.** `streamingStreamdownPlugins` stays `{ math }`, for the reason code highlighting waits: rendering every partial state of a growing diagram would re-run Mermaid at each token and show a parse error for most of them. The switch happens in the same pass as the highlighting's, so a reply that ends draws its diagrams and colours its code together.
- **Mermaid loads in its own chunk, when first needed.** The plugin imports `mermaid` statically, and Mermaid is the largest dependency this would add. The plugin object is created behind a dynamic `import()` the first time a finished block names `mermaid`, so startup and a chat without diagrams load none of it. The chunk ships inside the app, so this works offline, as everything in the renderer must.
- **`securityLevel: "strict"`, the plugin's default.** Labels are escaped and click handlers are off, since the diagram text comes from a model, which can be prompted by a document's content. The SVG is rendered in the page, not in a sandboxed frame, so strict is the line that matters; it is not configurable.
- **The theme follows the app's.** Mermaid's `default` theme in light, `dark` in dark, passed through Streamdown's `mermaid.config`. [`theme-provider.tsx`](../../surfsense_local/frontend/src/components/theme-provider.tsx) works out the light or dark theme but exposes only the preference, which can be `system`, and an OS change updates only the document's class. So its context gains `resolvedTheme`, set wherever it sets that class, the OS change under `system` included. The config keeps its identity per theme, so only a theme change redraws the diagrams.
- **An error shows the source.** A diagram Mermaid cannot parse renders as its code block through `mermaid.errorComponent`, with one translated line saying it could not be drawn, so a reader keeps what the model wrote. `suppressErrorRendering` stays on, so Mermaid's own error SVG never shows.
- **Exports are not touched.** A Studio document's Word and PDF outputs keep the block as code. Drawing diagrams into those files is a separate change.

## Not decided here

- Whether the agent's prompts should invite diagrams. This proposal only renders what a reply already contains.
- The surfsense_web component. It stays as it is until the hosted code goes.

## Checks

- **Bundle:** the size of the Mermaid chunk and the main chunk before and after, from `pnpm build`, posted on the implementation PR. Done when the main chunk grows by no more than the plugin's few kilobytes.
- **Tests:** `message.test.tsx` and `summary-viewer.test.tsx` assert that a finished `mermaid` block renders an SVG, that a streaming one stays code, and that an invalid one shows its source and the error line.
- **Manual:** a flowchart, a sequence diagram and a broken diagram, in light and dark, in a reply, a trace and a Studio document.
