import {
  createIntl,
  createIntlCache,
  type MessageFormatElement,
} from "react-intl"

import de from "./compiled/de.json"
import en from "./compiled/en.json"
import ja from "./compiled/ja.json"
import {
  BASE_LOCALE,
  isAppLocale,
  PSEUDO_LOCALE,
  type AppLocale,
  type Locale,
} from "./locales"

type Catalog = Record<FormatjsIntl.Message["ids"], MessageFormatElement[]>

// All three are bundled so text is there on the first render; a key a language
// lacks shows its English, never its id.
const catalogs: Record<Locale, Catalog> = {
  en: en as Catalog,
  ja: { ...(en as Catalog), ...(ja as Catalog) },
  de: { ...(en as Catalog), ...(de as Catalog) },
}

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
