import { statfs } from "node:fs/promises"

import { dialog, ipcMain, type BrowserWindow } from "electron"

import type { StorageKind } from "./marker.ts"
import { entriesToMove, planMove, type MovePlan } from "./plan-move.ts"
import type { ResolvedStorage } from "./resolve-storage.ts"
import { MoveFailedError, runMove } from "./run-move.ts"

const kindFrom = (value: unknown): StorageKind | null =>
  value === "data" || value === "models" ? value : null

async function freeBytesOf(path: string): Promise<number | null> {
  try {
    const stats = await statfs(path)
    return stats.bavail * stats.bsize
  } catch {
    return null
  }
}

/**
 * The renderer names a kind and never a path: main opens the picker and keeps
 * the plan, so a compromised page cannot point the mover at a folder of its own.
 */
export function registerStorageHandlers(options: {
  storage: ResolvedStorage
  modelsUnavailable: boolean
  appFolder: string
  isTrusted: (sender: Electron.WebContents) => boolean
  mainWindow: () => BrowserWindow | null
  /** Ask about running replies; false if the user stayed. */
  confirmStop: () => Promise<boolean>
  /** Stop every sidecar, so nothing writes while the files move. */
  stop: () => Promise<void>
  relaunch: () => void
  onMovingChange: (moving: boolean) => void
}): void {
  const { storage, modelsUnavailable, appFolder, isTrusted, mainWindow, confirmStop, stop, relaunch, onMovingChange } = options
  const { baseDir } = storage
  let pending: MovePlan | null = null
  let running: AbortController | null = null

  const send = (progress: unknown) => mainWindow()?.webContents.send("storage:progress", progress)

  const plan = async (kind: StorageKind, picked: string | null) => {
    const result = await planMove({ kind, picked, storage, appFolder })
    pending = "plan" in result ? result.plan : null
    if ("plan" in result) {
      const { toRoot, neededBytes, freeBytes, adopt } = result.plan
      return { status: "ready" as const, kind, target: toRoot, neededBytes, freeBytes, adopt }
    }
    return { status: "refused" as const, code: result.refused, neededBytes: result.neededBytes, freeBytes: result.freeBytes }
  }

  ipcMain.handle("storage:state", async (event) => {
    if (!isTrusted(event.sender)) return null
    return {
      data: {
        path: storage.dataRoot,
        isDefault: !storage.dataMoved,
        connected: true,
        freeBytes: await freeBytesOf(storage.dataRoot),
      },
      models: {
        path: storage.modelsRoot,
        isDefault: !storage.modelsMoved,
        connected: !modelsUnavailable,
        freeBytes: modelsUnavailable ? null : await freeBytesOf(storage.modelsRoot),
      },
    }
  })

  ipcMain.handle("storage:choose", async (event, value: unknown) => {
    const kind = kindFrom(value)
    const window = mainWindow()
    if (!isTrusted(event.sender) || kind === null || window === null) return { status: "canceled" }
    const { canceled, filePaths } = await dialog.showOpenDialog(window, {
      title: kind === "models" ? "Choose where to keep models" : "Choose where to keep your data",
      defaultPath: kind === "models" ? storage.modelsRoot : storage.dataRoot,
      // createDirectory is macOS's button; Windows and Linux dialogs always offer one.
      properties: ["openDirectory", "createDirectory", "dontAddToRecent"],
    })
    const picked = filePaths[0]
    if (canceled || picked === undefined) return { status: "canceled" }
    return plan(kind, picked)
  })

  ipcMain.handle("storage:plan-default", async (event, value: unknown) => {
    const kind = kindFrom(value)
    if (!isTrusted(event.sender) || kind === null) return { status: "canceled" }
    return plan(kind, null)
  })

  ipcMain.handle("storage:start", async (event) => {
    if (!isTrusted(event.sender) || pending === null || running !== null) return false
    const chosen = pending
    if (!(await confirmStop())) return false
    pending = null
    running = new AbortController()
    onMovingChange(true)
    // First, so the page covers itself before its API goes away.
    send({ phase: "stopping" })
    await stop()
    // Listed again now the sidecars are stopped: a database's -wal may have gone with them.
    const current = { ...chosen, entries: entriesToMove(chosen.kind, chosen.fromRoot) }
    void runMove({ plan: current, baseDir, signal: running.signal, onProgress: send })
      .then(relaunch)
      .catch((error: unknown) => {
        onMovingChange(false)
        const reason = error instanceof MoveFailedError ? error.reason : "failed"
        // A cancelled move has nothing to say: restart on the folder it never left.
        if (reason === "canceled") relaunch()
        else send({ phase: "failed", reason })
      })
    return true
  })

  ipcMain.handle("storage:cancel", (event) => {
    if (isTrusted(event.sender)) running?.abort()
  })

  // After a failed move, whose sidecars stopped for it.
  ipcMain.handle("storage:restart", (event) => {
    if (isTrusted(event.sender)) relaunch()
  })
}

