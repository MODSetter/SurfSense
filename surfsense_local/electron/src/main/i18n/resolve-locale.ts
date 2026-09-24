import { BASE_LOCALE, isLocale, type Locale } from "./locales.ts"

export type LocalePreference = Locale | "system"

// "system" takes the first OS language the app ships, matched on its base
// language, so ja-JP and de-AT resolve without listing every region.
export function resolveLocale(
  preference: string,
  systemLanguages: readonly string[]
): Locale {
  if (preference !== "system" && isLocale(preference)) return preference
  for (const tag of systemLanguages) {
    const base = tag.split("-")[0]?.toLowerCase()
    if (base && isLocale(base)) return base
  }
  return BASE_LOCALE
}
