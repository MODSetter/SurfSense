import { join } from "node:path"

import { app, BrowserWindow, ipcMain, Menu, shell } from "electron"

import { managedOriginalPath } from "./document-files.mts"
import { getFreePort, waitForHealth } from "./net.ts"
import { ollamaSpec } from "./sidecars/ollama.ts"
import { exe } from "./sidecars/platform.ts"
import { apiSpec, workerSpec } from "./sidecars/python.ts"
import { startAll, stopAll, type Sidecars } from "./sidecars/supervisor.ts"
import type { SidecarContext, SidecarSpec } from "./sidecars/types.ts"
import { loadWindowState, saveWindowState } from "./window-state.ts"

const DEV_RENDERER_URL = "http://localhost:5173"

function allowedExternalUrl(url: string): string | null {
  try {
    const parsed = new URL(url)
    if (
      parsed.protocol === "https:" &&
      (parsed.hostname === "surfsense.com" ||
        parsed.hostname === "www.surfsense.com")
    ) {
      return parsed.href
    }
  } catch {
    return null
  }
  return null
}

function openAllowedExternal(url: string): void {
  const allowed = allowedExternalUrl(url)
  if (allowed) void shell.openExternal(allowed)
}

// Dev keeps its own dir so testing never leaks into the real install's ~/.surfsense.
const DATA_DIR = join(
  app.getPath("home"),
  app.isPackaged ? ".surfsense" : ".surfsense-dev"
)
// productName is "SurfSense", same as the legacy desktop app, so the default
// userData would be shared with it. Users run both during migration.
app.setPath("userData", join(DATA_DIR, "electron"))

let sidecars: Sidecars | null = null
let mainWindow: BrowserWindow | null = null
let shuttingDown = false

function onSidecarCrash(name: string, code: number | null): void {
  process.stderr.write(`[main] sidecar ${name} crashed (code=${code})\n`)
  // best-effort: let the renderer show an error instead of hanging
  BrowserWindow.getAllWindows()[0]?.webContents.send("sidecar:crashed", {
    name,
    code,
  })
}

async function bootSidecars(): Promise<{ apiUrl: string; dataDir: string }> {
  const host = "127.0.0.1"
  const packaged = app.isPackaged
  const apiPort = await getFreePort(host)
  const dataDir = DATA_DIR

  const ctx: SidecarContext = {
    packaged,
    // dev: backend sits next to electron/; packaged: frozen binaries in resources/
    backendDir: join(app.getAppPath(), "..", "backend"),
    binariesDir: process.resourcesPath,
    host,
    apiPort,
    dataDir,
    // Packaged: bundled embedding, voice, and parser packs. Dev: same staging dir.
    modelsDir: packaged
      ? join(process.resourcesPath, "models")
      : join(app.getAppPath(), "..", "backend", "models"),
    llmfitPath: packaged
      ? join(process.resourcesPath, "llmfit", exe("llmfit"))
      : join(app.getAppPath(), "llmfit", exe("llmfit")),
  }
  if (packaged) {
    ctx.ollamaPort = await getFreePort(host)
    ctx.ollamaModelsDir = join(dataDir, "ollama")
    ctx.ollamaUrl = `http://${host}:${ctx.ollamaPort}`
  }

  // ollamaSpec is null in dev (the developer runs their own `ollama serve`)
  const specs = [apiSpec(ctx), workerSpec(ctx), ollamaSpec(ctx)].filter(
    (s): s is SidecarSpec => s !== null
  )
  sidecars = startAll(specs, onSidecarCrash)

  // gate on the API only; fail fast if it dies during startup. Ollama is
  // best-effort (its state shows via /llm/providers; an early exit hits onSidecarCrash).
  await waitForHealth(host, apiPort, { child: sidecars.get("api") })
  return { apiUrl: `http://${host}:${apiPort}`, dataDir }
}

function registerDocumentHandlers(dataDir: string): void {
  const trusted = (sender: Electron.WebContents): boolean =>
    mainWindow !== null && sender === mainWindow.webContents

  ipcMain.handle("shell:titlebar-overlay", (event, overlay) => {
    if (
      !trusted(event.sender) ||
      event.senderFrame !== event.sender.mainFrame ||
      mainWindow === null
    ) {
      return
    }
    if (overlay == null || typeof overlay !== "object") return
    applyTitleBarOverlay(mainWindow, overlay)
  })

  ipcMain.handle("documents:open", async (event, workspaceId, documentId) => {
    if (
      !trusted(event.sender) ||
      event.senderFrame !== event.sender.mainFrame
    ) {
      return "The source request did not come from the application."
    }
    try {
      const path = await managedOriginalPath(dataDir, workspaceId, documentId)
      return await shell.openPath(path)
    } catch (error) {
      return error instanceof Error
        ? error.message
        : "Couldn’t open the source."
    }
  })

  ipcMain.handle("shell:open-external", async (event, url) => {
    if (
      !trusted(event.sender) ||
      event.senderFrame !== event.sender.mainFrame ||
      typeof url !== "string"
    ) {
      return
    }
    const allowed = allowedExternalUrl(url)
    if (allowed) await shell.openExternal(allowed)
  })

  ipcMain.handle("documents:reveal", async (event, workspaceId, documentId) => {
    if (
      !trusted(event.sender) ||
      event.senderFrame !== event.sender.mainFrame
    ) {
      return "The source request did not come from the application."
    }
    try {
      const path = await managedOriginalPath(dataDir, workspaceId, documentId)
      shell.showItemInFolder(path)
      return ""
    } catch (error) {
      return error instanceof Error
        ? error.message
        : "Couldn’t locate the source."
    }
  })
}

function applyTitleBarOverlay(
  win: BrowserWindow,
  overlay: { color?: string; symbolColor?: string }
): void {
  if (process.platform === "darwin") return
  win.setTitleBarOverlay({
    ...(typeof overlay.color === "string" ? { color: overlay.color } : {}),
    ...(typeof overlay.symbolColor === "string"
      ? { symbolColor: overlay.symbolColor }
      : {}),
  })
}

// Packaged only. Dev keeps Electron's default View menu (Cmd/Ctrl+R).
// https://www.electronjs.org/docs/latest/tutorial/application-menu
function installProductionMenu(): void {
  if (!app.isPackaged) return

  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(process.platform === "darwin" ? [{ role: "appMenu" as const }] : []),
      { role: "fileMenu" },
      { role: "editMenu" },
      {
        label: "View",
        submenu: [
          {
            label: "Reload",
            click: (_item, win) => {
              if (win instanceof BrowserWindow) win.reload()
            },
          },
          {
            label: "Force Reload",
            click: (_item, win) => {
              if (win instanceof BrowserWindow) {
                win.webContents.reloadIgnoringCache()
              }
            },
          },
          { role: "toggleDevTools" },
          { type: "separator" },
          { role: "resetZoom" },
          { role: "zoomIn" },
          { role: "zoomOut" },
          { type: "separator" },
          { role: "togglefullscreen" },
        ],
      },
      { role: "windowMenu" },
    ])
  )
}

function createWindow(apiUrl: string): void {
  const savedState = app.isPackaged ? loadWindowState() : null
  const win = new BrowserWindow({
    ...(savedState?.bounds ?? { width: 1280, height: 800 }),
    show: false,
    // https://www.electronjs.org/docs/latest/tutorial/custom-title-bar
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "hidden",
    ...(process.platform !== "darwin" && { titleBarOverlay: true }),
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      additionalArguments: [`--surfsense-api-url=${apiUrl}`],
    },
  })
  mainWindow = win
  win.on("closed", () => {
    if (mainWindow === win) mainWindow = null
  })

  if (app.isPackaged) {
    win.on("close", () => saveWindowState(win))
  }

  win.once("ready-to-show", () => {
    if (app.isPackaged && (savedState?.maximized ?? true)) {
      win.maximize()
    }
    win.show()
  })

  if (app.isPackaged) {
    void win.loadFile(
      join(app.getAppPath(), "..", "frontend", "dist", "index.html")
    )
  } else {
    void win.loadURL(DEV_RENDERER_URL)
  }
}

async function shutdown(): Promise<void> {
  if (shuttingDown) return
  shuttingDown = true
  if (sidecars) await stopAll(sidecars)
}

function denyAppWindows(contents: Electron.WebContents): void {
  contents.setWindowOpenHandler(({ url }) => {
    openAllowedExternal(url)
    return { action: "deny" }
  })
  contents.on("will-navigate", (event, url) => {
    if (!url.startsWith("https:")) return
    event.preventDefault()
    openAllowedExternal(url)
  })
}

function main(): void {
  app.on("web-contents-created", (_event, contents) => {
    denyAppWindows(contents)
  })
  app
    .whenReady()
    .then(async () => {
      const boot = await bootSidecars()
      registerDocumentHandlers(boot.dataDir)
      installProductionMenu()
      createWindow(boot.apiUrl)
      app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0)
          createWindow(boot.apiUrl)
      })
    })
    .catch((err: unknown) => {
      process.stderr.write(`failed to start: ${String(err)}\n`)
      void shutdown().finally(() => app.exit(1))
    })

  app.on("window-all-closed", () => app.quit())

  // the single choke point that guarantees the sidecars die with the app
  app.on("before-quit", (event) => {
    if (!sidecars || shuttingDown) return
    event.preventDefault()
    void shutdown().finally(() => app.quit())
  })

  // Ctrl-C / dev loop: before-quit does not fire on a signal, so reap here too
  for (const sig of ["SIGINT", "SIGTERM"] as const) {
    process.on(sig, () => void shutdown().finally(() => app.exit(0)))
  }
}

// one app, one set of sidecars: a second instance would fight over the SQLite
// file and the port, so hand off to the primary window and quit
if (app.requestSingleInstanceLock()) {
  app.on("second-instance", () => {
    const win = BrowserWindow.getAllWindows()[0]
    if (!win) return
    if (win.isMinimized()) win.restore()
    win.focus()
  })
  main()
} else {
  app.quit()
}
