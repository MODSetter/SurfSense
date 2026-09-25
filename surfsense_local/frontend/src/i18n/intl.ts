import {
  createIntl,
  createIntlCache,
  type MessageFormatElement,
} from "react-intl"

import {
  BASE_LOCALE,
  isAppLocale,
  LOCALES,
  PSEUDO_LOCALE,
  type AppLocale,
  type Locale,
} from "./locales"

type Catalog = Record<FormatjsIntl.Message["ids"], MessageFormatElement[]>

// A glob, not an import per language, so shipping one more language is a line
// in LOCALES and a catalog file. `pnpm translations` writes compiled/. The
// pseudo-locale is excluded here and read below, so it cannot reach a build.
const compiled = import.meta.glob<Catalog>(
  ["./compiled/*.json", "!./compiled/en-XA.json"],
  { eager: true, import: "default" }
)

const english = compiled[`./compiled/${BASE_LOCALE}.json`] ?? {}

// Every language is bundled so text is there on the first render, and each is
// merged over English, so a key it lacks shows its English, never its id.
const catalogs = Object.fromEntries(
  LOCALES.map((locale) => [
    locale,
    locale === BASE_LOCALE
      ? english
      : { ...english, ...compiled[`./compiled/${locale}.json`] },
  ])
) as Record<Locale, Catalog>

// Main owns the language and preload reports it before the first paint. No
// bridge (tests, a bare `vite`) or a language the app does not ship is English.
function reportedLocale(): AppLocale {
  const reported = window.surfsense?.locale?.get()
  return reported !== undefined && isAppLocale(reported)
    ? reported
    : BASE_LOCALE
}

const locale = reportedLocale()

// `pnpm dev` alone writes the pseudo catalog, so a glob, not an import: it is
// empty when the file is absent, and a production build never reads it.
const pseudo = import.meta.env.DEV
  ? import.meta.glob<Catalog>("./compiled/en-XA.json", {
      eager: true,
      import: "default",
    })["./compiled/en-XA.json"]
  : undefined

const messages =
  import.meta.env.DEV && locale === PSEUDO_LOCALE
    ? (pseudo ?? catalogs.en)
    : catalogs[locale as Locale]

// One instance for the page's life: a language change reloads the window.
export const intl = createIntl(
  { locale, defaultLocale: BASE_LOCALE, messages },
  createIntlCache()
)
