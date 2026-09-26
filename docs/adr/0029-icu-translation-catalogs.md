# ADR 0029: Interface text lives in ICU MessageFormat catalogs, one flat JSON file per language

- **Status:** Accepted
- **Date:** 2026-09-24
- **Source:** [localization proposal L49–116](https://github.com/MODSetter/SurfSense/blob/c03b68aaa4986d3f2cc5ba98dfb192f72c93f884/docs/proposals/localization.md#L49-L116), [FormatJS ICU syntax](https://formatjs.github.io/docs/core-concepts/icu-syntax), commit [c3edca1b9](https://github.com/MODSetter/SurfSense/commit/c3edca1b9d44de178e7d8338d4a0b80144cd6fc7)

## Context

The desktop app's interface was English written into components. Japanese and German were next ([`03-international.md`](../../plans/community-local/seo/03-international.md)), and more languages would follow. The translations had to outlive whichever library renders them, be written by an agent and reviewed by anyone who reads the language, and survive plurals and word order that differ from English. Localization as built is in [localization](../architecture/localization.md).

## Decision

- One file per language in `surfsense_local/frontend/translations/`, a flat `{"id": "ICU string"}`. No nesting, no `common` block. `en.json` is generated from the code ([ADR 0030](0030-formatjs-renders-interface-text.md)); the others are written by translators.
- Messages are ICU MessageFormat 1: named placeholders, `plural` with each language's CLDR categories and `#`, `select`, and tags for styled parts of a sentence.
- Ids are `<feature>_<surface>_<purpose>`: the feature folder, then the component, then what the text does. Each place gets its own id, even when the English repeats.
- A value is a whole sentence. No joining two messages, no pieces around a link.
- Keys sorted with a two-space indent, the layout `formatjs extract` writes, the same order in every language.

## Consequences

- FormatJS, i18next with `i18next-icu`, Lingui and every major translation platform read the files, so the library can change without rewriting a translation.
- Word order stays with the translator: Japanese and German move placeholders and tags where their grammar needs them.
- Repetition in `en.json` is expected, and a feature's ids leave with the feature.
- The files hold no translator notes: the `simple` format has no field for them, and the key and the calling component, where the English is written, are the context.
