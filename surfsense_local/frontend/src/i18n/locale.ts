import { intl } from "./intl"
import { isAppLocale } from "./locales"

// The renderer follows main's language. A change reloads the window, and the
// reloaded page builds its intl in the new language from what preload reports.
export function followMainLocale(
  reload: () => void = () => window.location.reload()
): void {
  document.documentElement.lang = intl.locale
  window.surfsense?.locale?.onChange((next) => {
    if (isAppLocale(next) && next !== intl.locale) reload()
  })
}
