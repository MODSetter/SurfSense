import { ipcMain } from "electron"

import { databaseIdentity } from "./database-identity.ts"

// Sync: the page asks while it draws its first frame, before any request returns.
export function registerStartupFrameHandlers(options: {
  dataDir: string
  isTrusted: (sender: Electron.WebContents) => boolean
}): void {
  const { dataDir, isTrusted } = options
  ipcMain.on("startup:database-identity", (event) => {
    event.returnValue = isTrusted(event.sender)
      ? databaseIdentity(dataDir)
      : null
  })
}
