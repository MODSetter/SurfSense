---
status: proposed
code:
  - surfsense_local/frontend/translations/
  - surfsense_local/frontend/src/i18n/
  - surfsense_local/electron/src/main/i18n/
  - .agents/skills/translate/
  - scripts/check_translations.mjs
---

# Localization

> The desktop app's interface in English, Japanese and German, chosen from the OS languages or by the user. Translations are ICU MessageFormat JSON files in the repo, precompiled and bundled into the app, so nothing is fetched at run time and the build needs no network. FormatJS renders them, through its documented APIs only.

## Languages

English is the source. Japanese and German come first, in the order [`03-international.md`](../../plans/community-local/seo/03-international.md) set for the website: Japan is the second-largest market with no competitor on `ローカルLLM`, and Germany the largest non-English "alternative" demand. French, Spanish and Brazilian Portuguese are the next tier there and are added here as files only when the website's pages in those languages exist.

## What gets translated

Only text written into the app's own code. Anything a user or a model produces, and anything the backend sends as data, is shown as it is.

| Translated | Not translated |
|---|---|
| Labels, buttons, headings, menus, tooltips, placeholders, empty states, toasts, dialogs | User content: workspace, document and thread names, file contents, chat messages |
| Text read aloud or shown on hover: `aria-label`, `title`, `alt` | Model output: chat answers and Studio artifacts |
| Fixed sentences with a value inserted, `Deleted {name}` or a plural; the sentence is translated, the value is passed in unchanged | Backend and manifest data: model names and descriptions, provider names, file paths |
| The frontend's message for each backend error code (see [Backend text](#backend-text)) | Product and technical names: SurfSense, Studio, llama.cpp, GGUF |
| Main-process menu labels (see [Main process](#main-process)) | Logs, console output and developer-only text |

Model descriptions in the manifest are fixed text, but they reach the frontend as data from the backend, so they stay English. Translating them is catalog work, not part of this proposal.

The language a chat answer or a Studio output is written in is also out of scope. The chat already answers in the question's language ([chat](../architecture/chat.md)), and a podcast brief carries its own `language` ([Studio](../architecture/studio.md)). Both are independent of the interface language.

## Library

[FormatJS](https://formatjs.github.io/): `react-intl` in the renderer, `@formatjs/intl` (the same engine without React) in Electron main, `@formatjs/cli` at build time. Weighed against:

| Library | Why not |
|---|---|
| Paraglide JS 2 | built first, then replaced. Its ICU support is a separate inlang plugin (`@inlang/plugin-icu1`, first released Jan 2026) that inlang recommends loading from a CDN; loading it from `node_modules` works offline but is an off-default setting. inlang removed its lint rules in 2.0, and native rich text needs inlang's own file format. |
| Lingui 5 | its macros need Babel or SWC, which Rolldown cannot run; Vite 8 and `@vitejs/plugin-react` 6 would have to bring one back |
| react-i18next | not ICU without a plugin; keys untyped; the usual Electron setup loads JSON over IPC at run time, a problem a bundled app does not have |

What decides it for an air-gapped app: FormatJS reads ICU natively and is plain npm packages pinned by the lockfile, so an offline, reproducible build is its default rather than a setting to protect. It has shipped since 2014 (react-intl, about 2.3M weekly downloads in Sep 2026), and rich text, number and date formatting, and a translation checker (`formatjs verify`) are built in.

Measured on the 740 real strings in three languages: all catalogs cost about 48 KB gzipped (react-intl without its parser 8 KB, precompiled catalogs 40 KB), and a message formats in about 1 µs, so a screen's text takes well under a millisecond. Paraglide was about 10% faster per message and the same size gzipped; neither difference is visible.

## Keeping the library replaceable

**Files are ICU MessageFormat 1.** One JSON file per language, `{"key": "ICU string"}`: `plural`, `select`, `selectordinal`, `=n`, `#`, number and date formatters, and rich-text tags. FormatJS reads them natively; i18next with `i18next-icu`, Lingui and every major translation platform read the same files.

**Names are generic.**

```
surfsense_local/frontend/
  translations/             en.json, ja.json, de.json (ICU source)
  src/i18n/
    compiled/               formatjs compile-folder output, gitignored
    locales.ts              the languages that ship
    intl.ts                 the page's one IntlShape, all catalogs bundled
    message-ids.d.ts        FormatjsIntl.Message: ids are the keys of en.json
    locale.ts               follow main's language; reload on a change
surfsense_local/electron/src/main/i18n/
  locales.ts                mirror of the frontend's list
  app-locale.ts             main's IntlShape for the menu
  resolve-locale.ts         preference + OS languages → locale
  locale-prefs.ts           locale-prefs.json in userData
  locale-ipc.ts             locale:get, locale:preference, locale:set
```

**Call sites use FormatJS's own API.** `intl.formatMessage({ id: "sources_delete_confirm_title" }, { name })`, with `intl` imported from `@/i18n/intl`. It is one `createIntl` instance for the page's life, provided to React with `RawIntlProvider`, the pattern the FormatJS docs give for precompiled catalogs; code outside components uses the same instance. A language change reloads the window, so the instance never goes stale. ESLint forbids importing `compiled/` or the catalogs outside `src/i18n/`.

**The locale belongs to the app.** Main owns it; the renderer is told. The IPC channel and the stored preference never name the library.

## Shape of `en.json`

```json
{
  "chat_composer_placeholder": "Ask about your sources",
  "chat_composer_send_button": "Send",
  "chat_error_provider_auth": "Your model connection needs a new API key.",
  "settings_general_language_label": "Language",
  "sources_delete_cancel_button": "Cancel",
  "sources_delete_confirm_body": "Delete {count, plural, one {# document} other {# documents}}? This cannot be undone.",
  "sources_delete_confirm_title": "Delete “{name}”?",
  "sources_list_empty": "No documents yet. Add a file or a folder to start."
}
```

**Keys.** `<feature>_<surface>_<purpose>`, snake_case.

- `<feature>` is a folder under `src/features/` (`chat`, `sources`, `settings`), or `app` for the shell and `menu` for main. A check fails on any other prefix, so deleting a feature's folder shows its keys as dead.
- `<surface>` is the component or dialog: `composer`, `delete`, `list`.
- `<purpose>` names what the text does, never what it says: `_title`, `_body`, `_label`, `_placeholder`, `_button`, `_tooltip`, `_empty`, `_error`, `_toast`, `_aria`, `_link`, `_status`. The suffix tells a translator how much room there is. `sources_delete_confirm_title`, not `are_you_sure`.
- The text for a backend code is `<feature>_error_<code>`, the code as the backend sends it: `chat_error_provider_auth`.
- A key names the meaning, as [Locize](https://www.locize.com/blog/guide-to-i18n-key-naming) and [Lokalise](https://lokalise.com/blog/translation-keys-naming-and-organizing/) recommend. Rewording that keeps the meaning keeps the key and the skill retranslates it; a new meaning is a new key.

**No shared strings.** "Cancel" in a delete dialog and "Cancel" in a download are two keys. German may want *Abbrechen* in one and *Verwerfen* in the other, and a feature's keys leave with the feature. Repetition in `en.json` is expected; a `common` block is not allowed.

**Whole sentences.** A value is a sentence or a label, never a piece of one. No joining two keys, no leading or trailing space, no label ending in a colon followed by a value in code. Japanese puts the verb last and German moves it, so a sentence built from parts cannot be translated. A value inserted mid-sentence is a named placeholder: `{name}`, `{count}`, `{size}`, never `{0}`.

**Plurals and choices are ICU.** `{count, plural, one {# document} other {# documents}}`; FormatJS prints `#` with the language's digit grouping (12,345; 12.345). `=0` only when zero reads differently ("No documents"). Never `(s)`, never a `_one` and `_other` key pair. Each language writes the categories its CLDR rules have: Japanese only `other`, German `one` and `other`.

**Literal ids only.** Code calls `intl.formatMessage({ id: "sources_list_empty" })`, never with a computed id. `message-ids.d.ts` makes an id outside `en.json` a type error. A backend code maps to text through a typed record, so a new code without a message is a type error:

```ts
const chatErrorText: Record<ChatErrorKind, () => string> = {
  provider_auth: () => intl.formatMessage({ id: "chat_error_provider_auth" }),
  // one entry per ChatErrorKind
}
```

**Sorted.** Keys in each file sorted, tab-indented, one key per line, the same order in every language. A feature's keys sit together, diffs stay small, and two pull requests adding keys to different features rarely conflict. The check fails on an unsorted file.

**Other languages** hold exactly the keys of `en.json`: none missing, none extra. At run time each language's catalog is merged over English, so a missing key would show English, never its id.

## Locale

- **Detect.** On first launch, the first entry of `app.getPreferredSystemLanguages()` whose base language is supported (`ja-JP` → `ja`), else `en`.
- **Override.** Settings › General gets a Language select beside Appearance: System, English, 日本語, Deutsch, each language written in itself. The choice is saved as `locale-prefs.json` in `userData`, the way [`theme-prefs.ts`](../../surfsense_local/electron/src/main/theme-prefs.ts) saves the theme.
- **Hand over.** Preload reads the locale synchronously before the renderer's first paint, as it does the system theme, and exposes `locale.get()`, `locale.preference()`, `locale.set()` and `locale.onChange()`. `src/i18n/intl.ts` builds the page's `IntlShape` from `locale.get()` at load, with all three precompiled catalogs bundled, so text is there on the first render with no loading step.
- **Change.** Main saves the choice, calls `installProductionMenu()` again and tells the window, which reloads; the reloaded page builds its `IntlShape` in the new language. Open dialogs and other in-memory state reset; people rarely switch languages. No restart.
- **Formatting.** Numbers, dates, relative times, lists and language names go through `intl.formatNumber`, `formatDate`, `formatRelativeTime`, `formatList` and `formatDisplayName`, which cache formatters per language.
- **Html.** `<html lang>` follows the locale, so the OS picks the right CJK glyphs and screen readers the right voice.

## Main process

Main shows three strings of its own: the View menu's "View", "Reload" and "Force Reload" in [`electron/src/main/index.ts`](../../surfsense_local/electron/src/main/index.ts). `app-locale.ts` builds an `IntlShape` with `@formatjs/intl` from the same `translations/` files, imported directly and parsed at run time: three labels do not justify a compile step. Its own `message-ids.d.ts` types the ids.

The `role` menus (`appMenu`, `fileMenu`, `editMenu`, `windowMenu`) take their labels from Electron and the OS. On macOS they are only translated if the app ships that language's `.lproj`, so `mac.electronLanguages` in [`electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml) must include `en`, `ja` and `de` if it is ever narrowed ([electron#26231](https://github.com/electron/electron/issues/26231)).

## Backend text

The backend returns some English prose the UI shows as is: the chat's error messages in [`modules/chat/errors.py`](../../surfsense_local/backend/modules/chat/errors.py), the license rejection reasons in [`modules/license/router.py`](../../surfsense_local/backend/modules/license/router.py), and `detail` strings that [`lib/api.ts`](../../surfsense_local/frontend/src/lib/api.ts) surfaces. Where the backend sends a code (`provider_auth`, `bad_signature`), the frontend translates the code and falls back to the English text for a code it does not know. The backend stays English and gains no i18n.

## Build

`pnpm translations` runs `formatjs compile-folder translations src/i18n/compiled --format simple --ast`, before `dev`, `build`, `typecheck` and `test`. The AST output means no message is parsed at run time, so Vite aliases `@formatjs/icu-messageformat-parser` to its `no-parser` build, as the FormatJS performance guide describes. `compile-folder` fails the build on a malformed message, and `tsc -b` fails on an id that is not in `en.json`. Everything comes from npm and the lockfile; the build needs no network.

## Translating

1. **Developers write English only.** A new string is one line in `en.json` and an `intl.formatMessage({ id })` call.
2. **An agent translates.** The `translate` skill below fills in Japanese and German for every key that is new or whose English changed.
3. **Review is open.** Anyone who reads the language can correct a translation in a pull request; no release waits on it.
4. **Two pre-commit hooks guard the files.** There is no pull request CI for `surfsense_local` yet, but [`code-quality.yml`](../../.github/workflows/code-quality.yml) runs every pre-commit hook on a non-draft pull request's changed files, so both run there too.
   - `formatjs-verify` is FormatJS's own check (`formatjs verify --missing-keys --extra-keys --structural-equality`): every key translated, no extra keys, the same placeholders and tags as English. pre-commit installs `@formatjs/cli` for it.
   - `check-translations` runs [`scripts/check_translations.mjs`](../../scripts/check_translations.mjs), the rules FormatJS does not know: the key shape and prefix, a key no code in the frontend or Electron main calls, a leading or trailing space, an unsorted file. No dependencies, since that job installs nothing and the runner ships Node.

No machine-translation service is used: the strings are not user data, but the app's position is that nothing leaves without a decision ([ADR 0017](../adr/0017-egress-off-by-default.md)), and a skill run by a developer is that decision.

## The `translate` skill

`.agents/skills/translate/`, top level, because it runs commands.

- **Glossary.** Terms that stay in English (SurfSense, Studio, llama.cpp), and the chosen term per language for the rest, taken from the per-language term table in `03-international.md` so the app and the website use the same words (`ローカルLLM`, `lokale KI`).
- **Tone.** Japanese in です/ます, the default in Microsoft's Japanese style guide, with the plain form for short labels and 〜してください for instructions. German in *du*, which macOS has used since Sierra; never mixed with *Sie*.
- **Steps.** Find the keys to translate: those missing from a language, and those whose English differs from `en.json` at the last commit that changed that language's file. Read the component that calls each changed key, translate it, keep every placeholder, tag and ICU branch, run both checks, stop on a failure.
- **Limits.** Never reword English. Never translate a key name, a placeholder or a tag name. Flag a string whose meaning is unclear instead of guessing.

## Rich text

A styled part of a sentence is an ICU tag, FormatJS's native rich text: `"Using <b>{name}</b> via {source}"`, rendered with `intl.formatMessage({ id }, { b: (chunks) => <span …>{chunks}</span> })`. Each language places the tag where its grammar needs it, and `formatjs verify` checks every language keeps the same tags. A value can also be an element, such as a `<RelativeTime>` in `"Last call: {time}"`. A link that is an action gets its own element and key rather than a tag inside a sentence.

## Build order

1. **Seam.** `src/i18n/`, `translations/en.json`, the compile step, the lint rule, both checks, the preload bridge and the Language setting, with one feature moved to prove the path.
2. **Extract.** Move the remaining strings feature by feature under `src/features/`. The frontend has about 120 component files.
3. **Translate.** The skill, then `ja.json` and `de.json`.
4. **Ship.** Fold what is true into `docs/architecture/localization.md`, record the library choice and the ICU file format as ADRs, delete this proposal.
