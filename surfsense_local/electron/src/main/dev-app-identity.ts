import { join } from "node:path"

import { app } from "electron"

// Dev runs inside Electron's own bundle, so the Dock, taskbar and About panel
// would show Electron's name and icon. A "DEV" icon also keeps it apart from
// an installed SurfSense. Packaged builds get all of this from electron-builder.
const DEV_ICONS = join(__dirname, "../../build/icons/dev")
// Windows and Linux fill the canvas; the macOS Dock expects Apple's margin.
const DEV_ICON_PNG = join(DEV_ICONS, "icon.png")
const DEV_ICON_MACOS = join(DEV_ICONS, "icon-macos.png")
const DEV_NAME = "SurfSense Dev"

// safeStorage names its keychain item after the app, so dev must not share
// "SurfSense": it would read, or recreate, the installed app's key. Call
// before anything touches safeStorage.
export function nameDevBuild(): void {
  if (!app.isPackaged) app.setName(DEV_NAME)
}

export function applyDevAppIdentity(): void {
  if (app.isPackaged) return
  if (process.platform === "darwin") {
    app.dock?.setIcon(DEV_ICON_MACOS)
  }
  if (process.platform === "win32") {
    // Its own taskbar group, not electron.exe's or the installed app's.
    app.setAppUserModelId("com.surfsense.app.dev")
  }
  // iconPath is Linux and Windows only: macOS takes the panel's icon from the
  // bundle, so it stays Electron's in dev. `version` replaces Electron's build
  // number in the parentheses.
  app.setAboutPanelOptions({
    applicationName: DEV_NAME,
    applicationVersion: app.getVersion(),
    version: app.getVersion(),
    iconPath: DEV_ICON_PNG,
  })
}

// Windows takes the taskbar icon from the window; Linux takes the window icon.
export function devWindowIcon(): { icon?: string } {
  if (app.isPackaged || process.platform === "darwin") return {}
  return {
    icon: process.platform === "win32" ? join(DEV_ICONS, "icon.ico") : DEV_ICON_PNG,
  }
}
