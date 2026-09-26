import { app, ipcMain } from "electron"

import { appDetails } from "./app-details.ts"

export function registerAboutHandlers(): void {
  ipcMain.handle("about:details", () =>
    appDetails({
      version: app.getVersion(),
      versions: {
        electron: process.versions.electron,
        chrome: process.versions.chrome,
        node: process.versions.node,
      },
      platform: process.platform,
      systemVersion: process.getSystemVersion(),
      arch: process.arch,
    })
  )
}
