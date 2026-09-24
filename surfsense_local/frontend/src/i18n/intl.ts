import {
  createIntl,
  createIntlCache,
  type MessageFormatElement,
} from "react-intl"

import de from "./compiled/de.json"
import en from "./compiled/en.json"
import ja from "./compiled/ja.json"
import { BASE_LOCALE, isLocale, type Locale } from "./locales"

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
function reportedLocale(): Locale {
  const reported = window.surfsense?.locale?.get()
  return reported !== undefined && isLocale(reported) ? reported : BASE_LOCALE
}

const locale = reportedLocale()

// One instance for the page's life: a language change reloads the window.
export const intl = createIntl(
  { locale, defaultLocale: BASE_LOCALE, messages: catalogs[locale] },
  createIntlCache()
)
