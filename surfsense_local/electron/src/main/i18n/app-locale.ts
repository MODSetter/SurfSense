import { createIntl, createIntlCache, type IntlShape } from "@formatjs/intl"
import { app } from "electron"

import de from "../../../../frontend/translations/de.json"
import en from "../../../../frontend/translations/en.json"
import ja from "../../../../frontend/translations/ja.json"
import { PSEUDO_LOCALE, type AppLocale } from "./locales.ts"
import { resolveLocale, type LocalePreference } from "./resolve-locale.ts"

// Main reads the same ICU catalogs as the renderer. It formats three menu
// labels, so it parses them at run time instead of precompiling. Those labels
// stay English under the pseudo-locale, which only the renderer compiles.
const catalogs: Record<AppLocale, Record<string, string>> = {
  en,
  ja: { ...en, ...ja },
  de: { ...en, ...de },
  [PSEUDO_LOCALE]: en,
}
const cache = createIntlCache()

let current: IntlShape = createIntl({ locale: "en", messages: en }, cache)

// Main owns the interface language; windows are told through IPC.
export function applyLocalePreference(preference: LocalePreference): AppLocale {
  const locale =
    preference === PSEUDO_LOCALE
      ? PSEUDO_LOCALE
      : resolveLocale(preference, app.getPreferredSystemLanguages())
  current = createIntl(
    { locale, defaultLocale: "en", messages: catalogs[locale] },
    cache
  )
  return locale
}

export function currentLocale(): AppLocale {
  return current.locale as AppLocale
}

export function mainIntl(): IntlShape {
  return current
}
