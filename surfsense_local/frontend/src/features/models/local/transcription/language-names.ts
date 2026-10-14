import { intl } from "@/i18n/intl"

export type NamedLanguage = { code: string; name: string }

/** A language code named in the interface's language. */
export function languageName(code: string): string {
  try {
    return intl.formatDisplayName(code, { type: "language" }) ?? code
  } catch {
    // A code Intl cannot parse is still the best name there is.
    return code
  }
}

/** Alphabetical in the interface's language, so a reader finds their own. */
export function namedLanguages(codes: readonly string[]): NamedLanguage[] {
  return codes
    .map((code) => ({ code, name: languageName(code) }))
    .sort((a, b) => a.name.localeCompare(b.name, intl.locale))
}

/** The listed languages as one sentence-ready list. */
export function listLanguages(codes: readonly string[]): string {
  return intl.formatList(
    namedLanguages(codes).map(({ name }) => name),
    { type: "conjunction" }
  )
}
