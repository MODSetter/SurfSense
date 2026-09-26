# ADR 0030: FormatJS renders interface text from precompiled, bundled catalogs, with no network at build or run time

- **Status:** Accepted
- **Date:** 2026-09-25
- **Source:** [localization proposal L35–47](https://github.com/MODSetter/SurfSense/blob/c03b68aaa4986d3f2cc5ba98dfb192f72c93f884/docs/proposals/localization.md#L35-L47), [inlang: installing plugins](https://inlang.com/docs/install-plugin), [FormatJS performance guide](https://github.com/formatjs/formatjs/blob/main/docs/src/docs/guides/performance.mdx), commit [c03b68aaa](https://github.com/MODSetter/SurfSense/commit/c03b68aaa4986d3f2cc5ba98dfb192f72c93f884)

## Context

The app is air-gapped, so no translation may be fetched at run time, and a release build should come only from the lockfile. The catalogs are ICU ([ADR 0029](0029-icu-translation-catalogs.md)). Paraglide JS was built first: it compiles messages to typed functions, but reads ICU only through a separate inlang plugin, first released in January 2026, that inlang recommends loading from a CDN; loading it from `node_modules` is supported but described as local-only. inlang also removed its lint rules in 2.0, and its native rich text needs inlang's own format. Localization as built is in [localization](../architecture/localization.md).

## Decision

- `react-intl` renders the frontend and `@formatjs/cli` compiles and checks the catalogs. Both come from npm, pinned by the lockfile.
- Electron main translates nothing. Its application menu is Electron roles only, labelled by Electron and the OS; translating the few labels main writes itself mixed two languages in one menu.
- `formatjs compile-folder --ast` precompiles the catalogs before every build, and Vite aliases the ICU parser to its no-parser build.
- All three languages are bundled. One `createIntl` instance serves the page, given to React through `RawIntlProvider`, and a language change reloads the window.
- Messages are declared inline with their usage, as the FormatJS docs recommend: `intl.formatMessage({ id, defaultMessage }, values)`, with an explicit id and no wrapper. `formatjs extract` generates `en.json` from them, and `@formatjs/unplugin` strips `defaultMessage` from the bundle.
- FormatJS's ESLint plugin checks every call: English present (`enforce-default-message`), every placeholder given (`enforce-placeholders`), the id shape (`enforce-id`). Ids are typed through `FormatjsIntl.Message`, keyed on `en.json`.

## Consequences

- The build needs no network, and text is on screen at the first render. Measured on the real catalogs: about 48 KB gzipped for all three languages, about 1 µs per message.
- Rich text, formatting, extraction, `verify` and the lint rules are FormatJS's own, so the project keeps only a plural-category test and a short check for its id prefix and file layout.
- `en.json` cannot hold a message the code does not use, or miss one it does.
- The English sits next to where it is shown, which makes calls longer.
- A language change drops in-memory state such as an open dialog.
- Replacing FormatJS means rewriting every call site; the catalogs stay.
