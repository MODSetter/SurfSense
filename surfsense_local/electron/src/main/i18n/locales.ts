// Mirrors frontend/src/i18n/locales.ts: the languages with a catalog in
// frontend/translations/.
export const LOCALES = [
  "en",
  "de",
  "es",
  "fr",
  "hi",
  "ja",
  "ko",
  "pt-BR",
  "ru",
  "zh-CN",
] as const
export type Locale = (typeof LOCALES)[number]
export const BASE_LOCALE: Locale = "en"

// FormatJS's pseudo-locale, accepted only while the app is not packaged.
export const PSEUDO_LOCALE = "en-XA"
export type AppLocale = Locale | typeof PSEUDO_LOCALE

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value)
}
