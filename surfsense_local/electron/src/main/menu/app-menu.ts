import type { MenuItemConstructorOptions } from "electron"

// macOS only. Electron's own appMenu with Check for Updates… added; that label,
// like Help's, is English in every language.
export function appMenu(actions: {
  checkForUpdates: () => void
}): MenuItemConstructorOptions {
  return {
    role: "appMenu",
    submenu: [
      { role: "about" },
      { label: "Check for Updates…", click: () => actions.checkForUpdates() },
      { type: "separator" },
      { role: "services" },
      { type: "separator" },
      { role: "hide" },
      { role: "hideOthers" },
      { role: "unhide" },
      { type: "separator" },
      { role: "quit" },
    ],
  }
}
