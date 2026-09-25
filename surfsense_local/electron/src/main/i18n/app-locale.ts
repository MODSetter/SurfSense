import { app } from "electron"

import { PSEUDO_LOCALE, type AppLocale } from "./locales.ts"
import { resolveLocale, type LocalePreference } from "./resolve-locale.ts"

let current: AppLocale = "en"

// Main owns the interface language; windows are told through IPC and
// translate it themselves.
export function applyLocalePreference(preference: LocalePreference): AppLocale {
  current =
    preference === PSEUDO_LOCALE
      ? PSEUDO_LOCALE
      : resolveLocale(preference, app.getPreferredSystemLanguages())
  return current
}

export function currentLocale(): AppLocale {
  return current
}
