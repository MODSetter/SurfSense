import { intl } from "./intl"
import { isAppLocale } from "./locales"
import { localeSource } from "./locale-source"

// The page follows the source's language: main's on the desktop, the browser's
// otherwise. A change reloads it, and the reloaded page builds its intl anew.
export function followLocale(
  reload: () => void = () => window.location.reload()
): void {
  document.documentElement.lang = intl.locale
  localeSource().onChange((next) => {
    if (isAppLocale(next) && next !== intl.locale) reload()
  })
}
