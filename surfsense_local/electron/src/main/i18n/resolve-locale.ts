import {
  BASE_LOCALE,
  isLocale,
  type AppLocale,
  type Locale,
} from "./locales.ts"

export type LocalePreference = AppLocale | "system"

// "system" takes the first OS language the app ships, matched on its base
// language, so ja-JP and de-AT resolve without listing every region.
export function resolveLocale(
  preference: string,
  systemLanguages: readonly string[]
): Locale {
  if (preference !== "system" && isLocale(preference)) return preference
  for (const tag of systemLanguages) {
    const locale = catalogFor(tag)
    if (locale) return locale
  }
  return BASE_LOCALE
}

// Script and region subtags that ask for Traditional Chinese, which has no catalog.
const TRADITIONAL = new Set(["hant", "tw", "hk", "mo"])

// Two catalogs are regional: any Portuguese gets Brazilian, and Chinese gets
// Simplified unless the tag asks for Traditional.
function catalogFor(tag: string): Locale | undefined {
  const [base, ...rest] = tag.toLowerCase().split("-")
  if (base === "pt") return "pt-BR"
  if (base === "zh") {
    return rest.some((part) => TRADITIONAL.has(part)) ? undefined : "zh-CN"
  }
  return base && isLocale(base) ? base : undefined
}
