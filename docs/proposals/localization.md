---
status: proposed
code:
  - surfsense_local/frontend/translations/
  - surfsense_local/frontend/translation-context.json
  - surfsense_local/frontend/translations.inlang/
  - surfsense_local/frontend/src/i18n/
  - surfsense_local/electron/src/main/i18n/
  - .agents/skills/translate/
---

# Localization

> The desktop app's interface in English, Japanese and German, chosen from the OS languages or by the user. Translations are JSON files in the repo, compiled into the app, so nothing is fetched at run time. Paraglide JS compiles them today; the files, folder names and call sites do not name it, so it can be replaced without touching components.

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

[Paraglide JS 2](https://github.com/opral/paraglide-js). Weighed against:

| Library | Runtime, gzipped | Why not |
|---|---|---|
| Paraglide JS 2 | about 1 KB; unused messages are tree-shaken | chosen |
| Lingui 5 | about 5 KB | its macros need Babel or SWC, which Rolldown cannot run; Vite 8 and `@vitejs/plugin-react` 6 would have to bring one back |
| react-i18next | 15 to 20 KB, plus i18next | the heaviest; the usual Electron setup (`i18next-electron-fs-backend`) loads JSON over IPC at run time, a problem a bundled app does not have; keys are untyped |
| react-intl (FormatJS) | about 18 KB | a runtime ICU parser for messages that can be compiled ahead |

Size matters less in an app loaded from disk. What decides it is that Paraglide compiles each message to a typed ES module function, which runs unchanged in the renderer (Vite) and in the main process (Node): a wrong key or parameter is a type error, and there is no provider or runtime state to keep in sync across the two processes.

## Keeping the library replaceable

Four layers. Only the build config knows the library.

**Files are ICU MessageFormat 1.** One JSON file per language, `{"key": "ICU string"}`, stored through inlang's [ICU MessageFormat v1 plugin](https://inlang.com/m/p7c8m1d2/plugin-inlang-icu-messageformat-1): `plural`, `select`, `selectordinal`, `=n`, `#` and number and date formatters. FormatJS, i18next with `i18next-icu`, Lingui and every major translation platform read the same files. inlang's own format writes plurals as `declarations`, `selectors` and `match` objects that only inlang reads, so it is not used.

**Names are generic.**

```
surfsense_local/frontend/
  translations/             en.json, ja.json, de.json
  translation-context.json  one line of context per key, for the translator
  translations.inlang/      settings.json: locales, plugin, pathPattern
  src/i18n/
    compiled/               compiler output, gitignored
    messages.ts             the only import the app uses
    locale.ts               supported locales, current locale, change locale
surfsense_local/electron/src/main/i18n/
  compiled/                 same messages, compiled for main, gitignored
  locale.ts                 detect, store and broadcast the locale
```

The inlang project folder must end in `.inlang`; the name before it is free. The compiler writes wherever `outdir` points. Replacing the library deletes `translations.inlang/` and the `compiled/` folders and rewrites `messages.ts`.

**Call sites use one shape.** Components call `messages.sources_delete_confirm_title({ name })`, one typed function per key, imported from `@/i18n`. That is what Paraglide emits; another library satisfies it with a typed proxy, `(params) => t("sources_delete_confirm_title", params)`, and no component changes. An ESLint `no-restricted-imports` rule forbids importing `compiled/` from outside `src/i18n/`.

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
- `<purpose>` names what the text does, never what it says: `_title`, `_body`, `_label`, `_placeholder`, `_button`, `_tooltip`, `_empty`, `_error`, `_toast`, `_aria`. The suffix tells a translator how much room there is. `sources_delete_confirm_title`, not `are_you_sure`.
- The text for a backend code is `<feature>_error_<code>`, the code as the backend sends it: `chat_error_provider_auth`.
- A key names the meaning. Rewording that keeps the meaning keeps the key and the skill retranslates it; a new meaning is a new key.

Paraglide's own docs recommend [random readable keys](https://paraglidejs.com/message-keys) (`penguin_purple_shoe`), so a key never has to be renamed when the interface moves. Keys here carry meaning instead, as [Locize](https://www.locize.com/blog/guide-to-i18n-key-naming) and [Lokalise](https://lokalise.com/blog/translation-keys-naming-and-organizing/) recommend: the feature prefix is what lets the check find a deleted feature's keys, and the key is the first context a translator sees. The cost is a rename when a string moves to another feature.

**No shared strings.** "Cancel" in a delete dialog and "Cancel" in a download are two keys. German may want *Abbrechen* in one and *Verwerfen* in the other, and a feature's keys leave with the feature. Repetition in `en.json` is expected; a `common` block is not allowed.

**Whole sentences.** A value is a sentence or a label, never a piece of one. No joining two keys, no leading or trailing space, no label ending in a colon followed by a value in code. Japanese puts the verb last and German moves it, so a sentence built from parts cannot be translated. A value inserted mid-sentence is a named placeholder: `{name}`, `{count}`, `{size}`, never `{0}`.

**Plurals and choices are ICU.** `{count, plural, one {# document} other {# documents}}`. `=0` only when zero reads differently ("No documents"). Never `(s)`, never a `_one` and `_other` key pair. Each language writes the categories its CLDR rules have: Japanese only `other`, German `one` and `other`. The file check compares against those categories, not against English's.

**Literal keys only.** Code calls `messages.sources_list_empty()`, never `messages[key]`. A backend code maps to text through a typed record, so a new code without a message is a type error:

```ts
const chatErrorMessage: Record<ChatErrorKind, () => string> = {
  provider_auth: messages.chat_error_provider_auth,
  // one entry per ChatErrorKind
}
```

**Sorted.** Keys in each file sorted, two-space indent, one key per line, the same order in every language. A feature's keys sit together, diffs stay small, and two pull requests adding keys to different features rarely conflict. A formatter writes it; the check fails on an unsorted file.

**Other languages** hold exactly the keys of `en.json`: none missing, none extra. A missing key shows English, never the key name.

**Context for the translator.** A key and its English do not always say enough: "Open" can be a verb or a state, and `{name}` can be a file or a workspace. `translation-context.json`, beside `translations/`, gives such a key one line on where it appears and what fills its placeholders:

```json
{
  "sources_delete_confirm_title": "Title of the dialog that deletes one source. {name} is the file name.",
  "sources_list_empty": "Shown in the Sources panel when the workspace has no documents."
}
```

It sits outside `translations/` so the compiler and any translation platform never read it as a language. Only the `translate` skill reads it. The check fails when a key with a placeholder, or a value of three words or fewer, has no entry, and when an entry names a key `en.json` does not have. Most guides also suggest screenshots; they are left out until a translator who is not an agent asks for them.

## Locale

- **Detect.** On first launch, the first entry of `app.getPreferredSystemLanguages()` whose base language is supported (`ja-JP` → `ja`), else `en`.
- **Override.** Settings › General gets a Language select beside Appearance: System, English, 日本語, Deutsch, each language written in itself. The choice is saved as `locale-prefs.json` in `userData`, the way [`theme-prefs.ts`](../../surfsense_local/electron/src/main/theme-prefs.ts) saves the theme.
- **Hand over.** Preload reads the locale synchronously before the renderer's first paint, as it does the system theme, and exposes `locale.set()` and `locale.onChange()`. `src/i18n/locale.ts` passes it to the compiled runtime with `overwriteGetLocale()`.
- **Change.** A change re-renders the React root under a new `key` and calls `installProductionMenu()` again in main. No restart.
- **Formatting.** Dates, numbers and relative times go through `Intl` with the current locale. The frontend calls `Intl` or `toLocale*` in 13 places today; each takes the locale from `src/i18n/locale.ts`.
- **Html.** `<html lang>` follows the locale, so the OS picks the right CJK glyphs and screen readers the right voice.

## Main process

Main shows three strings of its own: the View menu's "View", "Reload" and "Force Reload" in [`electron/src/main/index.ts`](../../surfsense_local/electron/src/main/index.ts). They are compiled from the same `translations/` into `src/main/i18n/compiled/`, as a step in `electron-vite build`. Main has one user, so a module-level locale behind `overwriteGetLocale()` is safe; the `AsyncLocalStorage` pattern Paraglide documents is for servers.

The `role` menus (`appMenu`, `fileMenu`, `editMenu`, `windowMenu`) take their labels from Electron and the OS. On macOS they are only translated if the app ships that language's `.lproj`, so `mac.electronLanguages` in [`electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml) must include `en`, `ja` and `de` if it is ever narrowed ([electron#26231](https://github.com/electron/electron/issues/26231)).

## Backend text

The backend returns some English prose the UI shows as is: the chat's error messages in [`modules/chat/errors.py`](../../surfsense_local/backend/modules/chat/errors.py), and `detail` strings that [`lib/api.ts`](../../surfsense_local/frontend/src/lib/api.ts) surfaces. The backend already sends a code with each (`provider_auth`, `egress_disabled`); the frontend translates the code and falls back to the English text for a code it does not know. The backend stays English and gains no i18n.

## Translating

1. **Developers write English only.** A new string is one line in `en.json` and a `messages.*()` call.
2. **An agent translates.** The `translate` skill below fills in Japanese and German for every key that is new or whose English changed.
3. **Review is open.** Anyone who reads the language can correct a translation in a pull request; no release waits on it.
4. **CI checks the files.** A script fails the build on anything [Shape of `en.json`](#shape-of-enjson) forbids: a key missing from or extra to a language, placeholders or select branches that differ from the English, plural categories that do not match the language's CLDR rules, a value with markup or a leading or trailing space, a key prefix that is not a feature, a key no code in the frontend or in Electron main calls, a key that needs context and has none, an unsorted file.

`pnpx @inlang/cli machine translate` is not used: it sends every string to an outside translation service. The strings are not user data, but the app's position is that nothing leaves without a decision ([ADR 0017](../adr/0017-egress-off-by-default.md)), and a skill run by a developer is that decision.

## The `translate` skill

`.agents/skills/translate/`, top level, because it runs commands.

- **Glossary.** Terms that stay in English (SurfSense, Studio, Workspace, llama.cpp), and the chosen term per language for the rest, taken from the per-language term table in `03-international.md` so the app and the website use the same words (`ローカルLLM`, `lokale KI`).
- **Tone.** Japanese in です/ます, the default in Microsoft's Japanese style guide, with the plain form for short labels and 〜してください for instructions. German in *du*, which macOS has used since Sierra; never mixed with *Sie*.
- **Steps.** Find the keys to translate: those missing from a language, and those whose English differs from `en.json` at the last commit that changed that language's file. Read each changed key's line in `translation-context.json`, translate the changed keys, keep every placeholder and ICU branch, run the file check, stop on a failure.
- **Limits.** Never reword English. Never translate a key name. Flag a string whose meaning is unclear instead of guessing.

## Rich text

A sentence with a link or bold span is where libraries differ most, and the ICU plugin stores tags as plain text. Splitting it into keys around the link breaks the whole-sentence rule, so the copy is written without it: the sentence stands alone and the action is its own button or link with its own key. The check fails on a value that contains markup.

## Build order

1. **Spike.** Confirm the ICU plugin compiles under Paraglide 2 with the Vite 8 plugin and under the CLI for main, and that `modules` in `settings.json` can point at a local copy of the plugin instead of jsDelivr, so a build needs no network. If either fails, fall back to inlang's JSON plugin with simple `{placeholder}` messages and keep plurals out until it is fixed.
2. **Seam.** `src/i18n/`, `translations/en.json`, `translation-context.json`, the lint rule, the file check and formatter, the preload bridge and the Language setting, with one feature moved to prove the path.
3. **Extract.** Move the remaining strings feature by feature, one pull request per feature under `src/features/`. The frontend has about 120 component files.
4. **Translate.** The skill, then `ja.json` and `de.json`.
5. **Ship.** Fold what is true into `docs/architecture/localization.md`, record the library choice and the ICU file format as ADRs, delete this proposal.
