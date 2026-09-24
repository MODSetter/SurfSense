import { BrowserWindow, ipcMain } from "electron"

import { applyLocalePreference, currentLocale } from "./app-locale.ts"
import {
  isLocalePreference,
  loadLocalePreference,
  saveLocalePreference,
} from "./locale-prefs.ts"

// `locale:get` is sync so preload has the language before the first paint,
// the same way it reads the system theme.
export function registerLocaleHandlers(options: {
  isTrusted: (sender: Electron.WebContents) => boolean
  onChange: () => void
}): void {
  ipcMain.on("locale:get", (event) => {
    event.returnValue = currentLocale()
  })

  ipcMain.handle("locale:preference", () => loadLocalePreference())

  ipcMain.handle("locale:set", (event, preference: unknown) => {
    if (!options.isTrusted(event.sender)) return
    if (!isLocalePreference(preference)) return
    saveLocalePreference(preference)
    const locale = applyLocalePreference(preference)
    options.onChange()
    for (const win of BrowserWindow.getAllWindows()) {
      win.webContents.send("locale:changed", locale)
    }
  })
}
