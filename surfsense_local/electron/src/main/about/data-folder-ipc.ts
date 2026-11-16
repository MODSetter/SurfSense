import { ipcMain, shell } from "electron"

// Where models, workspaces and settings live, which the install folder does not hold.
export function registerDataFolderHandlers(options: {
  dataDir: string
  isTrusted: (sender: Electron.WebContents) => boolean
}): void {
  const { dataDir, isTrusted } = options

  ipcMain.handle("about:data-folder", (event) =>
    isTrusted(event.sender) ? dataDir : null
  )

  // "" once opened, the OS's reason otherwise, as shell.openPath returns.
  ipcMain.handle("about:open-data-folder", async (event) => {
    if (!isTrusted(event.sender)) {
      return "The request did not come from the application."
    }
    return await shell.openPath(dataDir)
  })
}
