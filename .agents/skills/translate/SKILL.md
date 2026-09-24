---
name: translate
description: Adding, changing or translating interface strings in the SurfSense desktop app (surfsense_local). Use when writing a key in translations/en.json, moving hard-coded UI text into messages, or filling in ja.json and de.json. Owns the key shape, the tone per language and the glossary.
---

# Translate

The desktop app's interface text lives in `surfsense_local/frontend/translations/`, one ICU MessageFormat file per language. English is the source; Japanese and German are translated from it. Design: [`docs/proposals/localization.md`](../../../docs/proposals/localization.md) (or `docs/architecture/localization.md` once it ships).

| File | Holds |
|---|---|
| `translations/en.json`, `ja.json`, `de.json` | `{"key": "ICU string"}`, flat, sorted, tab-indented |
| [`glossary.md`](glossary.md) | terms that stay English, and the chosen term per language |

Only fixed text in the app's code is translated. Never user content, model output, model names or descriptions, file paths, or logs.

## Adding English

- Key: `<feature>_<surface>_<purpose>`, snake_case. `<feature>` is a folder under `frontend/src/features/`, or `app` for the shell, `menu` for Electron main. `<purpose>` is one of `_title`, `_body`, `_label`, `_placeholder`, `_button`, `_tooltip`, `_empty`, `_error`, `_toast`, `_aria`, `_link`, `_status`.
- Name the meaning, not the words: `sources_delete_confirm_title`, not `are_you_sure`.
- A backend error code maps to `<feature>_error_<code>`.
- One key per place. Never reuse another feature's "Cancel"; never add a `common` key.
- A whole sentence per value. No joining keys, no leading or trailing space. A link that is an action becomes its own key and its own element.
- Named placeholders only: `{name}`, `{count}`. Plurals are ICU: `{count, plural, one {# document} other {# documents}}`; FormatJS prints `#` with the language's digit grouping. Never `(s)`.
- Call it with FormatJS's own API and a literal id: `intl.formatMessage({ id: "sources_list_empty" })`, or `intl.formatMessage({ id }, { name })` with values. Import `intl` from `@/i18n/intl`. An id outside `en.json` is a type error.
- A styled part of a sentence (a bold name, an accent) is an ICU tag, FormatJS's native rich text: `"Using <b>{name}</b> via {source}"`, rendered with `intl.formatMessage({ id }, { b: (chunks) => <span …>{chunks}</span> })`. An element can also be a value: `{ time: <RelativeTime … /> }`.
- Numbers, dates, relative times, lists and language names go through `intl.formatNumber`, `formatDate`, `formatRelativeTime`, `formatList`, `formatDisplayName`, never a bare `Intl.*` or `toLocale*`.
- Keep the file sorted. Add the same key to `ja.json` and `de.json` in the same change, translated with the steps below.

## Translating

1. **Find the keys.** A key needs work in a language when it is missing there, or when its English changed since that language was last translated:

   ```bash
   cd surfsense_local/frontend
   base=$(git log -1 --format=%H -- translations/ja.json)
   git diff "$base" -- translations/en.json
   ```

   Repeat with `de.json`. Every added or changed line in that diff is a key to translate.
2. **Read the context.** The component that calls it (`grep -rn '"<key>"' src`). Translate the meaning in that place, not the English words.
3. **Translate.** Follow the tone below and [`glossary.md`](glossary.md). Keep every placeholder name, tag name and `select` branch exactly. Write the plural categories the language has, not the English ones: Japanese only `other`, German `one` and `other`.
4. **Check.** From `surfsense_local/frontend`: `pnpm exec formatjs verify "translations/*.json" --source-locale en --missing-keys --extra-keys --structural-equality`, then `node scripts/check_translations.mjs` from the repo root. The `formatjs-verify` and `check-translations` pre-commit hooks run the same. Stop and fix on any failure; do not commit around it.

## Tone

- **Japanese.** です/ます for sentences, the default in Microsoft's Japanese style guide. Plain form for short labels and buttons (`保存`, `削除`). 〜してください for instructions. Full-width punctuation (`。`, `、`), no space between Japanese and Latin text unless the product name needs it.
- **German.** *du*, as macOS has used since Sierra. Never *Sie*, never mixed. Capitalize *du* only at the start of a sentence. Buttons are infinitives (`Speichern`, `Löschen`).
- Both: as short as the English allows. A `_button` or `_label` has the room its English has.

## Limits

- Never reword English while translating. A problem with the English is a separate change.
- Never translate a key name, a placeholder name or a tag name.
- Never guess. When a key's meaning is unclear from its component, stop and say which key and why.
- Never send strings to an outside translation service or CLI. Nothing leaves without a decision ([ADR 0017](../../../docs/adr/0017-egress-off-by-default.md)).
- A new term that will recur goes into [`glossary.md`](glossary.md) in the same change.
