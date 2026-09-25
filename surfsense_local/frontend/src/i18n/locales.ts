// The languages the app ships; one catalog each in translations/.
// Mirrored in electron/src/main/i18n/locales.ts.
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

// FormatJS's accented, longer English, to spot overflow and text outside a
// message. Dev only: a production build never lists or accepts it.
export const PSEUDO_LOCALE = "en-XA"
export type AppLocale = Locale | typeof PSEUDO_LOCALE
export type LocalePreference = AppLocale | "system"

export const SELECTABLE_LOCALES: readonly AppLocale[] = import.meta.env.DEV
  ? [...LOCALES, PSEUDO_LOCALE]
  : LOCALES

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value)
}

export function isAppLocale(value: string): value is AppLocale {
  return isLocale(value) || (import.meta.env.DEV && value === PSEUDO_LOCALE)
}
