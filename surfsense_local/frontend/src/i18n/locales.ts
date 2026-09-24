// The languages the app ships; one catalog each in translations/.
// Mirrored in electron/src/main/i18n/locales.ts.
export const LOCALES = ["en", "ja", "de"] as const
export type Locale = (typeof LOCALES)[number]
export type LocalePreference = Locale | "system"
export const BASE_LOCALE: Locale = "en"

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value)
}
