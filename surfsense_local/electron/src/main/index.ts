import { join } from "node:path"

import { app, BrowserWindow } from "electron"

import { getFreePort, waitForHealth } from "./net"
import { startSidecars, stopSidecars, type Sidecars } from "./sidecars"

const DEV_API_PORT = 8000
const DEV_RENDERER_URL = "http://localhost:5173"

let sidecars: Sidecars | null = null
let shuttingDown = false

function onSidecarCrash(name: string, code: number | null): void {
  process.stderr.write(`[main] sidecar ${name} crashed (code=${code})\n`)
  // best-effort: let the renderer show an error instead of hanging
  BrowserWindow.getAllWindows()[0]?.webContents.send("sidecar:crashed", { name, code })
}

async function bootSidecars(): Promise<string> {
  const host = "127.0.0.1"
  const packaged = app.isPackaged
  const port = packaged ? await getFreePort(host) : DEV_API_PORT

  const dataDir = join(app.getPath("home"), ".surfsense")
  sidecars = startSidecars(
    {
      // dev: backend sits next to electron/; packaged: frozen binaries in resources/
      backendDir: join(app.getAppPath(), "..", "backend"),
      binariesDir: process.resourcesPath,
      host,
      port,
      dataDir,
      // Packaged only: the shipped model is read-only in resources/, Docling's
      // download needs somewhere writable. Dev leaves both at their defaults.
      modelsDir: packaged ? join(process.resourcesPath, "models") : undefined,
      hfHome: packaged ? join(dataDir, "hf") : undefined,
      packaged,
    },
    onSidecarCrash,
  )

  // fail fast if the API dies during startup, rather than polling the full timeout
  await waitForHealth(host, port, { child: sidecars.api })
  return `http://${host}:${port}`
}

function createWindow(apiUrl: string): void {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      additionalArguments: [`--surfsense-api-url=${apiUrl}`],
    },
  })

  win.once("ready-to-show", () => win.show())

  if (app.isPackaged) {
    void win.loadFile(join(app.getAppPath(), "..", "frontend", "dist", "index.html"))
  } else {
    void win.loadURL(DEV_RENDERER_URL)
  }
}

async function shutdown(): Promise<void> {
  if (shuttingDown) return
  shuttingDown = true
  if (sidecars) await stopSidecars(sidecars)
}

function main(): void {
  app
    .whenReady()
    .then(async () => {
      const apiUrl = await bootSidecars()
      createWindow(apiUrl)
      app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow(apiUrl)
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
