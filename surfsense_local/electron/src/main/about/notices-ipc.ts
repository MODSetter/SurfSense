import { existsSync } from "node:fs"
import { join } from "node:path"

// What `build:notices` writes to electron/licenses/ and packaging copies to resources/licenses/.
const NOTICES_FILE = "THIRD_PARTY_NOTICES.txt"

export function noticesPath(app: {
  packaged: boolean
  appPath: string
  resourcesPath: string
}): string {
  return join(app.packaged ? app.resourcesPath : app.appPath, "licenses", NOTICES_FILE)
}

/** The third-party notices, opened in the system's text viewer, for the app's own window only. */
export function registerNoticesHandlers(options: {
  ipc: Pick<Electron.IpcMain, "handle">
  file: string
  isTrusted: (sender: Electron.WebContents) => boolean
  openPath: (path: string) => Promise<string>
  exists?: (path: string) => boolean
}): void {
  const { ipc, file, isTrusted, openPath, exists = existsSync } = options

  // "" once opened, the reason otherwise, as shell.openPath returns.
  ipc.handle("about:open-notices", async (event) => {
    if (!isTrusted(event.sender) || event.senderFrame !== event.sender.mainFrame) {
      return "The request did not come from the application."
    }
    // Only a dev checkout that never ran `build:notices` lacks it; every release ships it.
    if (!exists(file)) return `${file} does not exist.`
    return await openPath(file)
  })
}
