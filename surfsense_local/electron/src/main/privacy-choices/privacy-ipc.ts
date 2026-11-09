import type { FirstRunChoices, PrivacyController } from "./privacy-controller.ts"

type Ipc = Pick<Electron.IpcMain, "handle">

function firstRunChoices(value: unknown): FirstRunChoices | null {
  if (typeof value !== "object" || value === null) return null
  const { updates, usageStatistics } = value as Record<string, unknown>
  return typeof updates === "boolean" && typeof usageStatistics === "boolean"
    ? { updates, usageStatistics }
    : null
}

/**
 * window.surfsense.privacy, for the app's own window in its main frame only: the
 * state names what was sent, and a switch here decides what is sent next.
 * setUpdatesAutomatic goes through the updates bridge's own channel.
 */
export function registerPrivacyHandlers(options: {
  ipc: Ipc
  isTrusted: (sender: Electron.WebContents) => boolean
  controller: PrivacyController
}): void {
  const { ipc, controller } = options
  const fromApp = (event: Electron.IpcMainInvokeEvent): boolean =>
    options.isTrusted(event.sender) && event.senderFrame === event.sender.mainFrame

  ipc.handle("privacy:state", (event) => (fromApp(event) ? controller.state() : null))
  ipc.handle("privacy:set-usage-statistics", (event, enabled: unknown) => {
    if (fromApp(event) && typeof enabled === "boolean") controller.setUsageStatistics(enabled)
  })
  ipc.handle("privacy:preview-usage-report", (event) =>
    fromApp(event) ? controller.previewUsageReport() : null
  )
  ipc.handle("privacy:complete-first-run", (event, choices: unknown) => {
    const valid = firstRunChoices(choices)
    if (fromApp(event) && valid) controller.completeFirstRun(valid)
  })
}
