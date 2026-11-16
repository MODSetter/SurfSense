import type { Updates } from "../updater.ts"
import type { PrivacyController } from "./privacy-controller.ts"

type Ipc = Pick<Electron.IpcMain, "handle">

/** window.surfsense.updates. Reading is open as before; acting is for the app's own window. */
export function registerUpdateHandlers(options: {
  ipc: Ipc
  isTrusted: (sender: Electron.WebContents) => boolean
  controller: PrivacyController
  updates: Updates
  /** Check now: any time, unless a policy turned updates off. */
  checkNow: () => void
}): void {
  const { ipc, isTrusted, controller, updates } = options

  ipc.handle("updates:prefs", () => controller.updatePrefs())
  ipc.handle("updates:set-automatic", (event, automatic: unknown) =>
    isTrusted(event.sender)
      ? controller.setUpdatesAutomatic(automatic === true)
      : controller.updatePrefs()
  )
  ipc.handle("updates:state", () => updates.state())
  ipc.handle("updates:check", (event) => {
    if (isTrusted(event.sender)) options.checkNow()
  })
  ipc.handle("updates:install", (event) => {
    if (isTrusted(event.sender)) updates.install()
  })
}
