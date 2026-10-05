# Localization

The desktop app's interface is in English, German, Spanish, French, Hindi, Japanese, Korean, Brazilian Portuguese, Russian and Simplified Chinese, chosen from the OS languages or in Settings. Translations are ICU MessageFormat catalogs in the repo, precompiled and bundled into the app, so nothing is fetched at run time and the build needs no network. FormatJS renders them.

**Code:** [`surfsense_local/frontend/translations/`](../../surfsense_local/frontend/translations/), [`surfsense_local/frontend/src/i18n/`](../../surfsense_local/frontend/src/i18n/), [`surfsense_local/electron/src/main/i18n/`](../../surfsense_local/electron/src/main/i18n/), [`scripts/check_translations.mjs`](../../scripts/check_translations.mjs), [`.agents/skills/translate/`](../../.agents/skills/translate/SKILL.md)
**Decisions:** [ADR 0029](../adr/0029-icu-translation-catalogs.md), [ADR 0030](../adr/0030-formatjs-renders-interface-text.md)

## What is translated

Only text written into the app's own code: labels, buttons, headings, in-app menus, tooltips, placeholders, empty states, toasts, dialogs, `aria-label`, `title` and `alt`, fixed sentences with a value inserted, and the frontend's text for a backend error code.

Not translated: user content (workspace, document and thread names, file contents, chat messages), model output, backend and manifest data (model names and descriptions, provider names, file paths), the application menu, product and technical names used alone (SurfSense, Studio, llama.cpp, GGUF), and logs. The language a chat answer or a Studio output is written in is set elsewhere ([chat](chat.md), [Studio](studio.md)).

English is the source. Japanese and German came first, in the order [`03-international.md`](../../plans/community-local/seo/03-international.md) set for the website; the rest are the languages the [README](../../README.md) is translated into. Arabic is not among them: it reads right to left, which needs `dir` on the document, logical properties in place of the left and right utility classes, and mirrored directional icons, none of which is built.

## Catalogs

One flat JSON file per language, `{"id": "ICU string"}`, keys sorted with a two-space indent, the same order in every file ([ADR 0029](../adr/0029-icu-translation-catalogs.md)). `en.json` is generated: `formatjs extract` reads every `defaultMessage` in the code. `ja.json` and `de.json` are written by the `translate` skill and reviewers.

```json
{
  "onboarding_model_ready_server_status": "Using <b>{name}</b> via {source}",
  "sources_delete_dialog_title": "Delete {count, plural, one {# source} other {# sources}}?"
}
```

- An id is `<feature>_<surface>_<purpose>`. `<feature>` is a folder under `src/features/`, or `app` for the shell. `<purpose>` is one of `title`, `body`, `label`, `placeholder`, `button`, `tooltip`, `empty`, `error`, `toast`, `aria`, `link`, `status`. A backend code is `<feature>_error_<code>`.
- Each place has its own id, even where the English repeats. There is no `common` block.
- A value is a whole sentence with named placeholders. Plurals are ICU `plural` with the language's CLDR categories and `#`; Japanese writes only `other`. Styled parts of a sentence are tags.
- Visible apostrophes are `’`: ICU uses `'` as its escape character.
- Numbers go in raw and the message formats them with an ICU skeleton, as FormatJS's best practices ask: `{size, number, ::unit/gigabyte .#}`, `{percent, number, ::percent}`, `{downloads, number, ::compact-short}`. Each language then writes 1,2 GB, 40 % or 1.2万 its own way.
- A count or position is `{count, number}`, never a plain `{count}`, which prints raw digits in every language. Identifiers stay plain on purpose: a chunk id (`#{id}`) and an HTTP status (`{status}`) are not amounts.
- A date goes in as a `Date` and the message formats it with a date skeleton: `{date, date, ::yyyyMMMd}` reads Oct 18, 2026, 18. Okt. 2026 or 2026年10月18日.
- A number shown outside any message, such as a `3 / 10` counter or a score, goes through `intl.formatNumber`.

## Rendering

- [`intl.ts`](../../surfsense_local/frontend/src/i18n/intl.ts) builds one `createIntl` instance for the page, in the language preload reports, with every precompiled catalog bundled and each merged over English. The catalogs come from a glob over `compiled/`, keyed by `LOCALES`, so a language is a catalog file and a line in that list rather than an import here; the pseudo-locale is excluded from the glob so it cannot reach a build. [`main.tsx`](../../surfsense_local/frontend/src/main.tsx) gives it to React through `RawIntlProvider`.
- Every call declares its English inline, as the FormatJS docs recommend: `intl.formatMessage({ id: "sources_list_empty", defaultMessage: "No sources yet" })`. The id is literal and explicit. [`message-ids.d.ts`](../../surfsense_local/frontend/src/i18n/message-ids.d.ts) types the ids through `FormatjsIntl.Message`, so an id outside `en.json` is a type error.
- The build strips `defaultMessage` (`@formatjs/unplugin` with `removeDefaultMessage`), so each message ships once, in the catalogs.
- Rich text is FormatJS's: `{ b: (chunks) => <span …>{chunks}</span> }` for a tag, and an element can be a value, such as `<RelativeTime>` in "Last call: {time}".
- Numbers, dates, relative times, lists and language names go through `intl.formatNumber`, `formatDate`, `formatRelativeTime`, `formatList` and `formatDisplayName`.
- ESLint forbids importing the catalogs or `compiled/` outside `src/i18n/`.

## Locale

- Main resolves it: a saved choice, else the first entry of `app.getPreferredSystemLanguages()` whose base language ships (`ja-JP` → `ja`), else English ([`resolve-locale.ts`](../../surfsense_local/electron/src/main/i18n/resolve-locale.ts)). Two catalogs are regional, so they are matched by hand: any Portuguese takes `pt-BR`, and Chinese takes `zh-CN` unless the tag names Traditional (`zh-TW`, `zh-HK`, `zh-MO`, `zh-Hant`), which has no catalog and falls through to the next system language. Simplified Chinese stays selectable in Settings either way.
- Settings › General has a Language select beside Appearance: Match system, then each language in its own name. The choice is `locale-prefs.json` in `userData`.
- Preload reads the locale synchronously before first paint and exposes `locale.get()`, `preference()`, `set()` and `onChange()`. `index.html` sets `<html lang>` in the first frame, and [`locale.ts`](../../surfsense_local/frontend/src/i18n/locale.ts) keeps it.
- A change saves the choice and reloads the window, which builds its `IntlShape` in the new language. In-memory state, such as an open dialog, resets.
- Development also lists FormatJS's pseudo-locale `en-XA`: accented English, about 40% longer and bracketed, so overflow, clipping and text outside a message show up without a translation. The renderer lists it only under Vite dev, and main accepts it only when the app is not packaged; a production bundle does not contain it.

## Main process

Main resolves the language ([`app-locale.ts`](../../surfsense_local/electron/src/main/i18n/app-locale.ts)) but translates nothing. The application menu is the same in dev and packaged builds, built from Electron `role`s, with Developer Tools added while unpackaged. Its labels come from Electron and the OS, never from the in-app choice; on macOS a per-app language is set in System Settings › Language & Region. Translating the few labels main wrote itself left one menu in two languages. The exceptions are in [`menu/`](../../surfsense_local/electron/src/main/menu/): the Help menu and the app menu's Check for Updates…. No role covers them, so they are English in every language, and a non-English Mac shows them in English. The OS localizes role labels on macOS only for languages whose `.lproj` ships, so `mac.electronLanguages` in [`electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml) must keep `en`, `ja` and `de` if it is ever narrowed ([electron#26231](https://github.com/electron/electron/issues/26231)).

## Backend text

The backend stays English. Where it sends a code with its prose, the frontend shows its own text for the code and falls back to the backend's English for a code it does not know: the chat's error kinds ([`chat-error-text.ts`](../../surfsense_local/frontend/src/features/chat/chat-error-text.ts)), the license rejection reasons ([`license-error-text.ts`](../../surfsense_local/frontend/src/features/license/license-error-text.ts)), and why a Studio format is unavailable, where `unavailable_code` names the missing model types, such as `needs_chat_image` ([`studio-unavailable-text.ts`](../../surfsense_local/frontend/src/features/studio/studio-unavailable-text.ts)); a create, a regenerate or a podcast brief refused for that reason carries the same code in its `409` ([`studio-error-text.ts`](../../surfsense_local/frontend/src/features/studio/studio-error-text.ts)); and a model install's events, where `code` names the step or the refusal and a refusal for disk space sends its sizes as raw bytes for the message to format ([`install-text.ts`](../../surfsense_local/frontend/src/features/models/local/installs/install-text.ts)). Each code has a whole sentence of its own, not a list joined from parts.

## Build

`pnpm translations` runs before `dev`, `build`, `typecheck` and `test`:

1. `formatjs extract` writes `translations/en.json` from every `defaultMessage` in `frontend/src`.
2. `formatjs compile-folder translations src/i18n/compiled --format simple --ast` precompiles the catalogs, failing on a malformed message.

Each step is also its own script, `pnpm translations:extract` and `pnpm translations:compile`. `dev` alone also runs `pnpm translations:pseudo`, `formatjs compile translations/en.json --ast --pseudo-locale en-XA`, which writes the pseudo-locale's catalog; `intl.ts` reads it through `import.meta.glob`, so a build without it still compiles.

Vite aliases `@formatjs/icu-messageformat-parser` to its no-parser build, since no message is parsed at run time. `compiled/` is gitignored. Everything comes from npm and the lockfile.

## Checks

- ESLint, with FormatJS's plugin: `enforce-default-message` (every call carries its English), `enforce-placeholders` (every placeholder gets a value), and `enforce-id` (ids match `<feature>_<surface>_<purpose>`). Beside them, `no-restricted-syntax` refuses a `formatMessage` whose values are not written out as an object literal, whether passed as a variable or spread in, because `enforce-placeholders` reads only a literal and would pass such a call with a placeholder unfilled.
- `formatjs-extract`, a pre-commit hook: re-runs extraction, so a commit whose `en.json` does not match the code fails as a modified file.
- `formatjs-verify`, a pre-commit hook: `pnpm translations:verify`, which runs `formatjs verify --missing-keys --extra-keys --structural-equality` over every catalog. Both formatjs hooks run the frontend's own scripts, so `@formatjs/cli`'s version lives only in its `package.json`.
- `check-translations`, a pre-commit hook: [`check_translations.mjs`](../../scripts/check_translations.mjs) for the rules FormatJS does not know: an id prefix that is not a feature folder or `app`, a leading or trailing space, a straight apostrophe, an unsorted file, a catalog with no entry in `LOCALES`, and an entry with no catalog. It reads `LOCALES` from `locales.ts` rather than keeping its own copy, where a stale list would skip a language in silence, and it compares the files with line endings normalised, since git checks them out as CRLF on Windows.
- [`plural-categories.test.ts`](../../surfsense_local/frontend/src/i18n/plural-categories.test.ts), in `pnpm test`, which [`desktop-tests.yml`](../../.github/workflows/desktop-tests.yml) runs on pull requests: every plural writes exactly the categories `Intl.PluralRules` gives its language. It runs over `LOCALES`, so a new language is covered without editing it.

[`code-quality.yml`](../../.github/workflows/code-quality.yml) runs the hooks on a non-draft pull request's changed files.

## Translating

Developers write English only, inline in the `formatMessage` call; `pnpm translations` or the pre-commit hook updates `en.json`. The [`translate`](../../.agents/skills/translate/SKILL.md) skill drafts Japanese and German for every id that is new or whose English changed, with its glossary and tone (です/ます; German *du*). Anyone who reads a language can correct it in a pull request; no release waits on review. No machine-translation service is used ([ADR 0017](../adr/0017-egress-off-by-default.md)).

## Known gaps

- Backend prose without a code stays English in every language: fit verdicts, `not_runnable_reason`, which an install refusing a searched file repeats, an embedder's failed check at install, the disk-space `detail` that `lib/api.ts` wraps in a translated sentence, and Studio's refusals other than a missing model, such as "already generating" and "nothing is running", which the panel shows under its translated alert title.
