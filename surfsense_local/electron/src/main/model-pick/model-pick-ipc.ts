type Ipc = Pick<Electron.IpcMain, "handle">
type ShowOpenDialog = (
  window: Electron.BrowserWindow,
  options: Electron.OpenDialogOptions
) => Promise<{ canceled: boolean; filePaths: string[] }>

export type ModelPickKind = "file" | "folder"

const kindFrom = (value: unknown): ModelPickKind | null =>
  value === "file" || value === "folder" ? value : null

// English, like the application menu: main's own text is not translated.
function dialogOptions(kind: ModelPickKind): Electron.OpenDialogOptions {
  if (kind === "folder") {
    return {
      title: "Choose a folder of GGUF models",
      properties: ["openDirectory", "dontAddToRecent"],
    }
  }
  return {
    title: "Choose a GGUF model",
    properties: ["openFile", "dontAddToRecent"],
    filters: [
      { name: "GGUF models", extensions: ["gguf"] },
      { name: "All files", extensions: ["*"] },
    ],
  }
}

/**
 * window.surfsense.models.pick: the system's own dialog, for a model that lives
 * where no scan looks. The page names a kind and gets back the one path the
 * person chose, or null. The API then reads that file's header and refuses what
 * the runtime cannot chat with; nothing is copied or moved.
 */
export function registerModelPickHandlers(options: {
  ipc: Ipc
  isTrusted: (sender: Electron.WebContents) => boolean
  mainWindow: () => Electron.BrowserWindow | null
  // Electron's `dialog.showOpenDialog`, passed in so this runs under node:test.
  showOpenDialog: ShowOpenDialog
}): void {
  const { ipc, isTrusted, mainWindow, showOpenDialog: show } = options
  ipc.handle("models:pick", async (event, value: unknown) => {
    const kind = kindFrom(value)
    const window = mainWindow()
    const fromApp = isTrusted(event.sender) && event.senderFrame === event.sender.mainFrame
    if (!fromApp || kind === null || window === null) return null
    const { canceled, filePaths } = await show(window, dialogOptions(kind))
    const picked = filePaths[0]
    return canceled || picked === undefined ? null : picked
  })
}
