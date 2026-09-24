// Mirrors frontend/src/i18n/locales.ts: the languages with a catalog in
// frontend/translations/.
export const LOCALES = ["en", "ja", "de"] as const
export type Locale = (typeof LOCALES)[number]
export const BASE_LOCALE: Locale = "en"

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value)
}
