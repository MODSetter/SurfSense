import { join } from "node:path"

import { app, BrowserWindow } from "electron"

import { getFreePort, waitForHealth } from "./net.ts"
import { ollamaSpec } from "./sidecars/ollama.ts"
import { apiSpec, workerSpec } from "./sidecars/python.ts"
import { startAll, stopAll, type Sidecars } from "./sidecars/supervisor.ts"
import type { SidecarContext, SidecarSpec } from "./sidecars/types.ts"

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
  const apiPort = packaged ? await getFreePort(host) : DEV_API_PORT
  const dataDir = join(app.getPath("home"), ".surfsense")

  const ctx: SidecarContext = {
    packaged,
    // dev: backend sits next to electron/; packaged: frozen binaries in resources/
    backendDir: join(app.getAppPath(), "..", "backend"),
    binariesDir: process.resourcesPath,
    host,
    apiPort,
    dataDir,
    // Packaged only: the shipped model is read-only in resources/, Docling's
    // download needs somewhere writable. Dev leaves both at their defaults.
    modelsDir: packaged ? join(process.resourcesPath, "models") : undefined,
    hfHome: packaged ? join(dataDir, "hf") : undefined,
  }
  if (packaged) {
    ctx.ollamaPort = await getFreePort(host)
    ctx.ollamaModelsDir = join(dataDir, "ollama")
    ctx.ollamaUrl = `http://${host}:${ctx.ollamaPort}`
  }

  // ollamaSpec is null in dev (the developer runs their own `ollama serve`)
  const specs = [apiSpec(ctx), workerSpec(ctx), ollamaSpec(ctx)].filter(
    (s): s is SidecarSpec => s !== null,
  )
  sidecars = startAll(specs, onSidecarCrash)

  // gate on the API only; fail fast if it dies during startup. Ollama is
  // best-effort (its state shows via /llm/providers; an early exit hits onSidecarCrash).
  await waitForHealth(host, apiPort, { child: sidecars.get("api") })
  return `http://${host}:${apiPort}`
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
  if (sidecars) await stopAll(sidecars)
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
