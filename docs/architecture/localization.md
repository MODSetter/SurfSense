# Localization

The desktop app's interface is in English, Japanese and German, chosen from the OS languages or in Settings. Translations are ICU MessageFormat catalogs in the repo, precompiled and bundled into the app, so nothing is fetched at run time and the build needs no network. FormatJS renders them.

**Code:** [`surfsense_local/frontend/translations/`](../../surfsense_local/frontend/translations/), [`surfsense_local/frontend/src/i18n/`](../../surfsense_local/frontend/src/i18n/), [`surfsense_local/electron/src/main/i18n/`](../../surfsense_local/electron/src/main/i18n/), [`scripts/check_translations.mjs`](../../scripts/check_translations.mjs), [`.agents/skills/translate/`](../../.agents/skills/translate/SKILL.md)
**Decisions:** [ADR 0029](../adr/0029-icu-translation-catalogs.md), [ADR 0030](../adr/0030-formatjs-renders-interface-text.md)

## What is translated

Only text written into the app's own code: labels, buttons, headings, menus, tooltips, placeholders, empty states, toasts, dialogs, `aria-label`, `title` and `alt`, fixed sentences with a value inserted, the frontend's text for a backend error code, and main's menu labels.

Not translated: user content (workspace, document and thread names, file contents, chat messages), model output, backend and manifest data (model names and descriptions, provider names, file paths), product and technical names used alone (SurfSense, Studio, llama.cpp, GGUF), and logs. The language a chat answer or a Studio output is written in is set elsewhere ([chat](chat.md), [Studio](studio.md)).

English is the source. Japanese and German came first, in the order [`03-international.md`](../../plans/community-local/seo/03-international.md) set for the website.

## Catalogs

One flat JSON file per language, `{"id": "ICU string"}`, keys sorted with a two-space indent, the same order in every file ([ADR 0029](../adr/0029-icu-translation-catalogs.md)). `en.json` is generated: `formatjs extract` reads every `defaultMessage` in the code. `ja.json` and `de.json` are written by the `translate` skill and reviewers.

```json
{
  "onboarding_model_ready_server_status": "Using <b>{name}</b> via {source}",
  "sources_delete_dialog_title": "Delete {count, plural, one {# source} other {# sources}}?"
}
```

- An id is `<feature>_<surface>_<purpose>`. `<feature>` is a folder under `src/features/`, or `app` for the shell and `menu` for main. `<purpose>` is one of `title`, `body`, `label`, `placeholder`, `button`, `tooltip`, `empty`, `error`, `toast`, `aria`, `link`, `status`. A backend code is `<feature>_error_<code>`.
- Each place has its own id, even where the English repeats. There is no `common` block.
- A value is a whole sentence with named placeholders. Plurals are ICU `plural` with the language's CLDR categories and `#`; Japanese writes only `other`. Styled parts of a sentence are tags.
- Visible apostrophes are `’`: ICU uses `'` as its escape character.
- Numbers go in raw and the message formats them with an ICU skeleton, as FormatJS's best practices ask: `{size, number, ::unit/gigabyte .#}`, `{percent, number, ::percent}`, `{downloads, number, ::compact-short}`. Each language then writes 1,2 GB, 40 % or 1.2万 its own way.
- A count or position is `{count, number}`, never a plain `{count}`, which prints raw digits in every language. Identifiers stay plain on purpose: a chunk id (`#{id}`) and an HTTP status (`{status}`) are not amounts.
- A date goes in as a `Date` and the message formats it with a date skeleton: `{date, date, ::yyyyMMMd}` reads Oct 18, 2026, 18. Okt. 2026 or 2026年10月18日.
- A number shown outside any message, such as a `3 / 10` counter or a score, goes through `intl.formatNumber`.

## Rendering

- [`intl.ts`](../../surfsense_local/frontend/src/i18n/intl.ts) builds one `createIntl` instance for the page, in the language preload reports, with all three precompiled catalogs bundled and each merged over English. [`main.tsx`](../../surfsense_local/frontend/src/main.tsx) gives it to React through `RawIntlProvider`.
- Every call declares its English inline, as the FormatJS docs recommend: `intl.formatMessage({ id: "sources_list_empty", defaultMessage: "No sources yet" })`. The id is literal and explicit. [`message-ids.d.ts`](../../surfsense_local/frontend/src/i18n/message-ids.d.ts) types the ids through `FormatjsIntl.Message`, so an id outside `en.json` is a type error.
- The build strips `defaultMessage` (`@formatjs/unplugin` with `removeDefaultMessage`), so each message ships once, in the catalogs.
- Rich text is FormatJS's: `{ b: (chunks) => <span …>{chunks}</span> }` for a tag, and an element can be a value, such as `<RelativeTime>` in "Last call: {time}".
- Numbers, dates, relative times, lists and language names go through `intl.formatNumber`, `formatDate`, `formatRelativeTime`, `formatList` and `formatDisplayName`.
- ESLint forbids importing the catalogs or `compiled/` outside `src/i18n/`.

## Locale

- Main resolves it: a saved choice, else the first entry of `app.getPreferredSystemLanguages()` whose base language ships (`ja-JP` → `ja`), else English ([`resolve-locale.ts`](../../surfsense_local/electron/src/main/i18n/resolve-locale.ts)).
- Settings › General has a Language select beside Appearance: Match system, then each language in its own name. The choice is `locale-prefs.json` in `userData`.
- Preload reads the locale synchronously before first paint and exposes `locale.get()`, `preference()`, `set()` and `onChange()`. `index.html` sets `<html lang>` in the first frame, and [`locale.ts`](../../surfsense_local/frontend/src/i18n/locale.ts) keeps it.
- A change saves the choice, rebuilds the menu, and reloads the window, which builds its `IntlShape` in the new language. In-memory state, such as an open dialog, resets.
- Development also lists FormatJS's pseudo-locale `en-XA`: accented English, about 40% longer and bracketed, so overflow, clipping and text outside a message show up without a translation. The renderer lists it only under Vite dev, and main accepts it only when the app is not packaged; a production bundle does not contain it. Main's menu labels stay English under it.

## Main process

[`app-locale.ts`](../../surfsense_local/electron/src/main/i18n/app-locale.ts) builds an `IntlShape` with `@formatjs/intl` from the same catalogs, imported directly and parsed at run time, for the View menu's three labels. The `role` menus take their labels from Electron and the OS; on macOS only for languages whose `.lproj` ships, so `mac.electronLanguages` in [`electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml) must keep `en`, `ja` and `de` if it is ever narrowed ([electron#26231](https://github.com/electron/electron/issues/26231)).

## Backend text

The backend stays English. Where it sends a code with its prose, the frontend shows its own text for the code and falls back to the backend's English for a code it does not know: the chat's error kinds ([`chat-error-text.ts`](../../surfsense_local/frontend/src/features/chat/chat-error-text.ts)) and the license rejection reasons ([`license-error-text.ts`](../../surfsense_local/frontend/src/features/license/license-error-text.ts)).

## Build

`pnpm translations` runs before `dev`, `build`, `typecheck` and `test`:

1. `formatjs extract` writes `translations/en.json` from every `defaultMessage` in `frontend/src` and `electron/src/main`.
2. `formatjs compile-folder translations src/i18n/compiled --format simple --ast` precompiles the catalogs, failing on a malformed message.

Each step is also its own script, `pnpm translations:extract` and `pnpm translations:compile`. `dev` alone also runs `pnpm translations:pseudo`, `formatjs compile translations/en.json --ast --pseudo-locale en-XA`, which writes the pseudo-locale's catalog; `intl.ts` reads it through `import.meta.glob`, so a build without it still compiles.

Vite aliases `@formatjs/icu-messageformat-parser` to its no-parser build, since no message is parsed at run time. `compiled/` is gitignored. Everything comes from npm and the lockfile.

## Checks

- ESLint, with FormatJS's plugin: `enforce-default-message` (every call carries its English), `enforce-placeholders` (every placeholder gets a value), and `enforce-id` (ids match `<feature>_<surface>_<purpose>`).
- `formatjs-extract`, a pre-commit hook: re-runs extraction, so a commit whose `en.json` does not match the code fails as a modified file.
- `formatjs-verify`, a pre-commit hook: `formatjs verify --missing-keys --extra-keys --structural-equality` over the three catalogs.
- `check-translations`, a pre-commit hook: [`check_translations.mjs`](../../scripts/check_translations.mjs) for the rules FormatJS does not know: an id prefix that is not a feature folder, `app` or `menu`, a leading or trailing space, a straight apostrophe, an unsorted file.
- [`plural-categories.test.ts`](../../surfsense_local/frontend/src/i18n/plural-categories.test.ts), in `pnpm test`: every plural writes exactly the categories `Intl.PluralRules` gives its language.

[`code-quality.yml`](../../.github/workflows/code-quality.yml) runs the hooks on a non-draft pull request's changed files.

## Translating

Developers write English only, inline in the `formatMessage` call; `pnpm translations` or the pre-commit hook updates `en.json`. The [`translate`](../../.agents/skills/translate/SKILL.md) skill drafts Japanese and German for every id that is new or whose English changed, with its glossary and tone (です/ます; German *du*). Anyone who reads a language can correct it in a pull request; no release waits on review. No machine-translation service is used ([ADR 0017](../adr/0017-egress-off-by-default.md)).

## Known gaps

- `enforce-placeholders` checks values only when they are passed as an object literal; a call that passes a variable, as `model-ready.tsx` does, is not checked.
- `plural-categories.test.ts` runs only in `pnpm test`, and no workflow runs the desktop tests on pull requests.
- Backend prose without a code stays English in every language: model install messages, fit verdicts, `not_runnable_reason`, a Studio format's `unavailable_reason`, and the disk-space `detail` that `lib/api.ts` wraps in a translated sentence.
- Studio's fallback "Needs {models}" joins translated noun phrases with `formatList`, so German case agreement is not guaranteed. It shows only when a format lacks the backend's `unavailable_reason`.
- A chat failure caught before the stream starts shows the `unknown` kind's text, not the error's own detail.
