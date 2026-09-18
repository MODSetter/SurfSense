import { readFileSync, renameSync, writeFileSync } from "node:fs"
import { join } from "node:path"

import { app } from "electron"

// Mirrors the Theme type in frontend/src/components/theme-provider.tsx.
export type ThemePreference = "dark" | "light" | "system"

const THEME_VALUES: ThemePreference[] = ["dark", "light", "system"]

function prefsPath(): string {
  return join(app.getPath("userData"), "theme-prefs.json")
}

function isThemePreference(value: unknown): value is ThemePreference {
  return (
    typeof value === "string" && THEME_VALUES.includes(value as ThemePreference)
  )
}

export function loadThemePreference(): ThemePreference {
  try {
    const parsed: unknown = JSON.parse(readFileSync(prefsPath(), "utf8"))
    const theme =
      parsed && typeof parsed === "object"
        ? (parsed as { theme?: unknown }).theme
        : undefined
    return isThemePreference(theme) ? theme : "system"
  } catch {
    return "system"
  }
}

export function saveThemePreference(theme: ThemePreference): void {
  try {
    const path = prefsPath()
    const temporary = `${path}.tmp`
    writeFileSync(temporary, JSON.stringify({ theme }))
    renameSync(temporary, path)
  } catch (error) {
    // ponytail: best-effort, same as window-state.ts; a stale/missing pref
    // just falls back to "system" next launch.
    process.stderr.write(
      `[main] failed to save theme preference: ${String(error)}\n`,
    )
  }
}
