import {
  askForMicrophone,
  microphoneAccess,
  openMicrophoneSettings,
  type SystemMicrophone,
} from "./system-access.ts"

/** The renderer's microphone bridge, for the app's own window, in its main frame only. */
export function registerMicrophoneHandlers(options: {
  ipc: Pick<Electron.IpcMain, "handle">
  isTrusted: (sender: Electron.WebContents) => boolean
  system: SystemMicrophone
}): void {
  const { ipc, system } = options
  const fromApp = (event: Electron.IpcMainInvokeEvent): boolean =>
    options.isTrusted(event.sender) &&
    event.senderFrame === event.sender.mainFrame

  ipc.handle("microphone:status", (event) =>
    fromApp(event) ? microphoneAccess(system) : "denied"
  )
  // Only the app may make macOS show its prompt.
  ipc.handle("microphone:request", (event) =>
    fromApp(event) ? askForMicrophone(system) : "denied"
  )
  ipc.handle("microphone:open-settings", (event) =>
    fromApp(event) ? openMicrophoneSettings(system) : false
  )
}
