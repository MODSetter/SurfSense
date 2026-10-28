import {
  isAppLocale,
  PSEUDO_LOCALE,
  type AppLocale,
  type LocalePreference,
} from "./locales"
import type { LocaleSource } from "./locale-source"
import { resolveLocale } from "./resolve-locale"

// What Electron's main does for the desktop, done by the browser: the choice is
// this browser's, so each device keeps its own.
export const LOCALE_KEY = "surfsense:locale:v1"

// A choice a failed write could not store, kept for the page's life.
let unsaved: LocalePreference | null = null

function storedPreference(): LocalePreference {
  if (unsaved !== null) return unsaved
  try {
    const stored = localStorage.getItem(LOCALE_KEY)
    return stored !== null && isAppLocale(stored) ? stored : "system"
  } catch {
    return "system"
  }
}

function currentLocale(): AppLocale {
  const preference = storedPreference()
  return preference === PSEUDO_LOCALE
    ? PSEUDO_LOCALE
    : resolveLocale(preference, navigator.languages)
}

const listeners = new Set<(locale: string) => void>()

function announce() {
  const locale = currentLocale()
  for (const listener of listeners) listener(locale)
}

export const browserLocale: LocaleSource = {
  get: currentLocale,
  preference: async () => storedPreference(),
  set: async (preference) => {
    const next: LocalePreference =
      preference !== "system" && isAppLocale(preference) ? preference : "system"
    try {
      localStorage.setItem(LOCALE_KEY, next)
      unsaved = null
    } catch {
      // Private browsing and full disks throw.
      unsaved = next
    }
    announce()
  },
  onChange: (listener) => {
    listeners.add(listener)
    // Another tab's choice, and the browser's own languages changing under "system".
    const fromStorage = (event: StorageEvent) => {
      if (event.key === LOCALE_KEY || event.key === null)
        listener(currentLocale())
    }
    const fromBrowser = () => listener(currentLocale())
    window.addEventListener("storage", fromStorage)
    window.addEventListener("languagechange", fromBrowser)
    return () => {
      listeners.delete(listener)
      window.removeEventListener("storage", fromStorage)
      window.removeEventListener("languagechange", fromBrowser)
    }
  },
}
