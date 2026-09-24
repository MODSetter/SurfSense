import { readFileSync, renameSync, writeFileSync } from "node:fs"
import { join } from "node:path"

import { app } from "electron"

import { isLocale } from "./locales.ts"
import type { LocalePreference } from "./resolve-locale.ts"

function prefsPath(): string {
  return join(app.getPath("userData"), "locale-prefs.json")
}

export function isLocalePreference(value: unknown): value is LocalePreference {
  return value === "system" || (typeof value === "string" && isLocale(value))
}

export function loadLocalePreference(): LocalePreference {
  try {
    const parsed: unknown = JSON.parse(readFileSync(prefsPath(), "utf8"))
    const locale =
      parsed && typeof parsed === "object"
        ? (parsed as { locale?: unknown }).locale
        : undefined
    return isLocalePreference(locale) ? locale : "system"
  } catch {
    return "system"
  }
}

export function saveLocalePreference(locale: LocalePreference): void {
  try {
    const path = prefsPath()
    const temporary = `${path}.tmp`
    writeFileSync(temporary, JSON.stringify({ locale }))
    renameSync(temporary, path)
  } catch (error) {
    // Best-effort, as theme-prefs.ts: a lost write falls back to "system".
    process.stderr.write(
      `[main] failed to save locale preference: ${String(error)}\n`
    )
  }
}
