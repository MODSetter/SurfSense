import { ipcMain } from "electron"

import { sessionLog } from "./session-log.ts"

// The log can name files and models, so only the app's own window may read it.
export function registerSessionLogHandlers(options: {
  isTrusted: (sender: Electron.WebContents) => boolean
}): void {
  ipcMain.handle("session-log:read", (event) =>
    options.isTrusted(event.sender) ? sessionLog.lines() : []
  )
}
