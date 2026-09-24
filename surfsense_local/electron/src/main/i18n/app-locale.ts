import { createIntl, createIntlCache, type IntlShape } from "@formatjs/intl"
import { app } from "electron"

import de from "../../../../frontend/translations/de.json"
import en from "../../../../frontend/translations/en.json"
import ja from "../../../../frontend/translations/ja.json"
import type { Locale } from "./locales.ts"
import { resolveLocale, type LocalePreference } from "./resolve-locale.ts"

// Main reads the same ICU catalogs as the renderer. It formats three menu
// labels, so it parses them at run time instead of precompiling.
const catalogs: Record<Locale, Record<string, string>> = {
  en,
  ja: { ...en, ...ja },
  de: { ...en, ...de },
}
const cache = createIntlCache()

let current: IntlShape = createIntl({ locale: "en", messages: en }, cache)

// Main owns the interface language; windows are told through IPC.
export function applyLocalePreference(preference: LocalePreference): Locale {
  const locale = resolveLocale(preference, app.getPreferredSystemLanguages())
  current = createIntl(
    { locale, defaultLocale: "en", messages: catalogs[locale] },
    cache
  )
  return locale
}

export function currentLocale(): Locale {
  return current.locale as Locale
}

export function mainIntl(): IntlShape {
  return current
}
