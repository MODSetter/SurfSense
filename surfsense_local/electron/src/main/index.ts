import { existsSync, mkdirSync, statSync } from "node:fs"
import { join } from "node:path"

import {
  app,
  BrowserWindow,
  ipcMain,
  Menu,
  nativeTheme,
  safeStorage,
  shell,
} from "electron"
// Static on purpose: electron-updater is CJS and exposes `autoUpdater` through
// a getter, which `await import()` cannot see (named export comes back
// undefined). require() honours it, and the getter is lazy so dev pays nothing.
import { autoUpdater } from "electron-updater"

import {
  applyDevAppIdentity,
  devWindowIcon,
  nameDevBuild,
} from "./dev-app-identity.ts"
import { managedOriginalPath } from "./document-files.ts"
import { allowedExternalUrl } from "./external-url.ts"
import { getFreePort, waitForHealth } from "./net.ts"
import { loadSecret } from "./secret.ts"
import {
  llamacppSpec,
  LLAMACPP_SIDECAR,
  PRESET_FILE,
} from "./sidecars/llamacpp.ts"
import {
  audiocppSpec,
  AUDIOCPP_SIDECAR,
  SERVER_CONFIG,
} from "./sidecars/audiocpp.ts"
import { apiSpec, workerSpec } from "./sidecars/python.ts"
import {
  binaryPath as sdcppBinaryPath,
  sdcppSpec,
  SDCPP_SIDECAR,
  type ImageRuntime,
} from "./sidecars/sdcpp.ts"
import {
  startAll,
  startOne,
  stopAll,
  stopNamed,
  type Sidecars,
} from "./sidecars/supervisor.ts"
import type { SidecarContext, SidecarSpec } from "./sidecars/types.ts"
import {
  attachUpdater,
  readUpdatePrefs,
  writeUpdatePrefs,
  type Updates,
  type UpdateState,
} from "./updater.ts"
import {
  loadThemePreference,
  saveThemePreference,
  type ThemePreference,
} from "./theme-prefs.ts"
import { loadWindowState, saveWindowState } from "./window-state.ts"
import { applyLocalePreference } from "./i18n/app-locale.ts"
import { loadLocalePreference } from "./i18n/locale-prefs.ts"
import { registerLocaleHandlers } from "./i18n/locale-ipc.ts"
import { registerAboutHandlers } from "./about/about-ipc.ts"
import { sessionLog } from "./session-log/session-log.ts"
import { registerSessionLogHandlers } from "./session-log/session-log-ipc.ts"
import { appMenu } from "./menu/app-menu.ts"
import { helpMenu } from "./menu/help-menu.ts"

const DEV_RENDERER_URL = "http://localhost:5173"

function openAllowedExternal(url: string): void {
  const allowed = allowedExternalUrl(url)
  if (allowed) void shell.openExternal(allowed)
}

nameDevBuild()

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

// sd-server takes its model as a startup argument and dies without one, so it
// cannot be started at boot like the others: the model arrives later, on a
// download, and changes again whenever a different one is chosen. The API is the
// authority on which weights that is, so follow it and restart on a change.
// ponytail: a poll, not a push. It costs one local request every few seconds and
// needs no IPC channel of its own; a change is user-initiated and rare, so the
// few seconds of lag are not felt.
function watchImageModel(ctx: SidecarContext): void {
  if (ctx.imageModelsDir == null) return
  const endpoint = `http://${ctx.host}:${ctx.apiPort}/llm/image/local/runtime`
  let current: string | null = null

  const reconcile = async () => {
    if (!sidecars || shuttingDown) return
    const response = await fetch(endpoint)
    if (!response.ok) return
    const runtime = (await response.json()) as ImageRuntime

    const spec = sdcppSpec(ctx, runtime)
    const wanted = spec ? spec.args.join("\u0000") : null
    if (wanted === current) return

    if (sidecars.has(SDCPP_SIDECAR)) await stopNamed(sidecars, SDCPP_SIDECAR)
    current = wanted
    if (spec) startOne(sidecars, spec, onSidecarCrash)
  }

  const timer = setInterval(() => {
    void reconcile().catch(() => {
      // The API is down or restarting; the next tick tries again.
    })
  }, 5000)
  timer.unref()
}

// llama-server reads its per-model arguments from a preset INI **once, at
// startup**: appending a section while it runs does not surface the model,
// measured. The API rewrites that file whenever it installs a model or reprices
// one, so the router has to be restarted to see it. Same shape as
// watchImageModel, and for the same reason: the API is the authority, and a
// change is user-initiated and rare.
function watchGenerationPreset(ctx: SidecarContext): void {
  if (ctx.llamacppModelsDir == null) return
  const preset = join(ctx.llamacppModelsDir, PRESET_FILE)
  let current = presetStamp(preset)

  const reconcile = async () => {
    if (!sidecars || shuttingDown) return
    const stamp = presetStamp(preset)
    if (stamp === current) return
    current = stamp

    if (sidecars.has(LLAMACPP_SIDECAR)) await stopNamed(sidecars, LLAMACPP_SIDECAR)
    const spec = llamacppSpec(ctx)
    if (spec) startOne(sidecars, spec, onSidecarCrash)
  }

  const timer = setInterval(() => {
    void reconcile().catch(() => {
      // Mid-write or mid-restart; the next tick tries again.
    })
  }, 5000)
  timer.unref()
}

// audio.cpp's server refuses an empty model list, so it runs only while the API's
// config names a model. The API rewrites that file on every audio install and
// delete, and removes it with the last model; follow it, as for the preset.
function watchAudioModels(ctx: SidecarContext): void {
  if (ctx.audioModelsDir == null) return
  const config = join(ctx.audioModelsDir, SERVER_CONFIG)
  let current = presetStamp(config)

  const reconcile = async () => {
    if (!sidecars || shuttingDown) return
    const stamp = presetStamp(config)
    if (stamp === current) return
    current = stamp

    if (sidecars.has(AUDIOCPP_SIDECAR)) await stopNamed(sidecars, AUDIOCPP_SIDECAR)
    const spec = audiocppSpec(ctx)
    if (spec) startOne(sidecars, spec, onSidecarCrash)
  }

  const timer = setInterval(() => {
    void reconcile().catch(() => {
      // Mid-write or mid-restart; the next tick tries again.
    })
  }, 5000)
  timer.unref()
}

/** Size and mtime, which is enough to notice a rewrite and costs no read. */
function presetStamp(path: string): string {
  try {
    const stats = statSync(path)
    return `${stats.size}:${stats.mtimeMs}`
  } catch {
    return "absent"
  }
}

async function bootSidecars(): Promise<{ apiUrl: string; dataDir: string }> {
  const host = "127.0.0.1"
  const packaged = app.isPackaged
  const apiPort = await getFreePort(host)
  const dataDir = DATA_DIR
  // Linux without a keyring daemon: keep booting on Chromium's built-in key
  // rather than refusing to start; same fallback every Electron app takes.
  if (process.platform === "linux") safeStorage.setUsePlainTextEncryption(true)

  const ctx: SidecarContext = {
    packaged,
    // dev: backend sits next to electron/; packaged: frozen binaries in resources/
    backendDir: join(app.getAppPath(), "..", "backend"),
    binariesDir: process.resourcesPath,
    host,
    apiPort,
    dataDir,
    secret: loadSecret(join(app.getPath("userData"), "secret.bin"), safeStorage),
    // Packaged: bundled embedding, voice, and parser packs. Dev: same staging dir.
    modelsDir: packaged
      ? join(process.resourcesPath, "models")
      : join(app.getAppPath(), "..", "backend", "models"),
    // The staged llama.cpp build, same bytes either way: `fetch-llamacpp.mjs`
    // writes electron/llamacpp/ and packaging copies that folder verbatim.
    llamacppBinariesDir: packaged
      ? join(process.resourcesPath, "llamacpp")
      : join(app.getAppPath(), "llamacpp"),
    // The staged audio.cpp build, same bytes either way, as for llama.cpp.
    audioBinariesDir: packaged
      ? join(process.resourcesPath, "audiocpp")
      : join(app.getAppPath(), "audiocpp"),
  }
  // Unconditional, because dev needs a runtime too and DATA_DIR already keeps
  // dev models out of the real install (~/.surfsense-dev).
  ctx.llamacppPort = await getFreePort(host)
  ctx.llamacppModelsDir = join(dataDir, "models")
  ctx.llamacppUrl = `http://${host}:${ctx.llamacppPort}`
  // llama-server exits 1 when --models-dir does not exist, and on a clean
  // install nothing has created it yet: only a download would, and a download
  // needs the runtime. Measured: "failed to initialize router models: error:
  // '<path>' does not exist or is not a directory".
  mkdirSync(ctx.llamacppModelsDir, { recursive: true })

  // Dev too, as for llama.cpp: podcasts are voiced by the binary that ships.
  ctx.audioPort = await getFreePort(host)
  ctx.audioUrl = `http://${host}:${ctx.audioPort}`
  ctx.audioModelsDir = join(dataDir, "audio")
  mkdirSync(ctx.audioModelsDir, { recursive: true })

  // Same staging in both modes, like llama.cpp. Only a host with a staged
  // sd-server gets an images dir: without one the API offers no image models,
  // rather than downloads that can never run.
  const sdcppBinariesDir = packaged
    ? join(process.resourcesPath, "sdcpp")
    : join(app.getAppPath(), "sdcpp")
  if (existsSync(sdcppBinaryPath({ ...ctx, sdcppBinariesDir }))) {
    ctx.sdcppBinariesDir = sdcppBinariesDir
    ctx.imagePort = await getFreePort(host)
    ctx.imageModelsDir = join(dataDir, "images")
    ctx.imageUrl = `http://${host}:${ctx.imagePort}`
  }

  // llamacppSpec is null in dev, where no binary is staged. sd-server is absent
  // here on purpose: watchImageModel owns it, because only the API knows which
  // model was chosen.
  const specs = [
    apiSpec(ctx),
    workerSpec(ctx, "ingest"),
    workerSpec(ctx, "studio"),
    llamacppSpec(ctx),
    // Null until the API's config names an audio model.
    audiocppSpec(ctx),
  ].filter(
    (s): s is SidecarSpec => s !== null
  )
  sidecars = startAll(specs, onSidecarCrash)
  watchImageModel(ctx)
  watchGenerationPreset(ctx)
  watchAudioModels(ctx)

  // gate on the API only; fail fast if it dies during startup. llama-server is
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

  ipcMain.handle("theme:set", (event, theme: unknown) => {
    if (
      !trusted(event.sender) ||
      event.senderFrame !== event.sender.mainFrame
    ) {
      return
    }
    if (theme !== "dark" && theme !== "light" && theme !== "system") return
    saveThemePreference(theme)
    applyBackgroundColorToAllWindows(theme)
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

// Updates are the one call the app makes on its own, so they are off until the
// user turns them on; "Check now" in Settings works either way.
async function registerUpdateHandlers(): Promise<void> {
  const prefsPath = join(app.getPath("userData"), "updates.json")
  const trusted = (sender: Electron.WebContents): boolean =>
    mainWindow !== null && sender === mainWindow.webContents
  const broadcast = (state: UpdateState) =>
    mainWindow?.webContents.send("updates:state", state)

  let updates: Updates
  if (app.isPackaged) {
    // GitHub's CDN rejects the multi-range requests differential updates need.
    autoUpdater.disableDifferentialDownload = true
    // Its default logger is the console, which a packaged app shows nowhere.
    const log = (message: unknown) => sessionLog.append("updater", String(message))
    autoUpdater.logger = { info: log, warn: log, error: log }
    updates = attachUpdater(autoUpdater, broadcast)
  } else {
    // ponytail: dev has no signed build to update; expose the same surface
    // so the Settings row renders, and stay idle.
    updates = {
      check: async () => undefined,
      install: () => undefined,
      state: () => ({ status: "idle" }),
    }
  }

  const check = (): void => {
    writeUpdatePrefs(prefsPath, {
      ...readUpdatePrefs(prefsPath),
      lastCheckedAt: new Date().toISOString(),
    })
    void updates.check()
  }

  ipcMain.handle("updates:prefs", () => readUpdatePrefs(prefsPath))
  ipcMain.handle("updates:set-automatic", (event, automatic: unknown) => {
    if (!trusted(event.sender)) return readUpdatePrefs(prefsPath)
    const prefs = { ...readUpdatePrefs(prefsPath), automatic: automatic === true }
    writeUpdatePrefs(prefsPath, prefs)
    return prefs
  })
  ipcMain.handle("updates:state", () => updates.state())
  ipcMain.handle("updates:check", (event) => {
    if (trusted(event.sender)) check()
  })
  ipcMain.handle("updates:install", (event) => {
    if (trusted(event.sender)) updates.install()
  })

  if (readUpdatePrefs(prefsPath).automatic) check()
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

// Mirrors --app-shell in frontend/src/index.css (:root / .dark). Used as the
// BrowserWindow's native backgroundColor so a reload shows the right theme
// immediately instead of flashing Electron's default opaque white while the
// page is torn down and reloaded.
// https://www.electronjs.org/docs/latest/api/browser-window#showing-window-gracefully
const APP_SHELL_LIGHT = "#f3f2ee"
const APP_SHELL_DARK = "#101010"

function resolveBackgroundColor(theme: ThemePreference): string {
  const resolvedDark =
    theme === "system" ? nativeTheme.shouldUseDarkColors : theme === "dark"
  return resolvedDark ? APP_SHELL_DARK : APP_SHELL_LIGHT
}

function currentWindows(): BrowserWindow[] {
  return BrowserWindow.getAllWindows()
}

function applyBackgroundColorToAllWindows(theme: ThemePreference): void {
  const color = resolveBackgroundColor(theme)
  for (const win of currentWindows()) win.setBackgroundColor(color)
}

// A menu action the window carries out, shown first in case it was hidden.
function sendToWindow(channel: string): void {
  if (!mainWindow) return
  mainWindow.show()
  mainWindow.webContents.send(channel)
}

// One menu in dev and packaged builds. Role labels come from Electron and the
// OS; the few items of ours are English. DevTools only unpackaged.
// https://www.electronjs.org/docs/latest/tutorial/application-menu
function installMenu(): void {
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(process.platform === "darwin"
        ? [
            appMenu({
              checkForUpdates: () => sendToWindow("updates:check-requested"),
            }),
          ]
        : []),
      { role: "fileMenu" },
      { role: "editMenu" },
      {
        role: "viewMenu",
        submenu: [
          { role: "reload" },
          { role: "forceReload" },
          ...(app.isPackaged ? [] : [{ role: "toggleDevTools" as const }]),
          { type: "separator" },
          { role: "resetZoom" },
          { role: "zoomIn" },
          { role: "zoomOut" },
          { type: "separator" },
          { role: "togglefullscreen" },
        ],
      },
      { role: "windowMenu" },
      helpMenu({
        version: app.getVersion(),
        openExternal: openAllowedExternal,
        reportIssue: () => sendToWindow("help:report-issue"),
      }),
    ])
  )
}

function createWindow(apiUrl: string): void {
  // Dev keeps its own copy under .surfsense-dev, so it never moves the packaged window.
  const savedState = loadWindowState()
  const win = new BrowserWindow({
    ...(savedState?.bounds ?? { width: 1280, height: 800 }),
    ...devWindowIcon(),
    backgroundColor: resolveBackgroundColor(loadThemePreference()),
    show: false,
    // https://www.electronjs.org/docs/latest/tutorial/custom-title-bar
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "hidden",
    ...(process.platform !== "darwin" && { titleBarOverlay: true }),
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      additionalArguments: [`--surfsense-api-url=${apiUrl}`],
      // https://www.electronjs.org/docs/latest/api/structures/web-preferences
      ...(app.isPackaged && { devTools: false }),
    },
  })
  mainWindow = win
  win.on("closed", () => {
    if (mainWindow === win) mainWindow = null
  })
  // Its info level is React's and Vite's development chatter.
  win.webContents.on("console-message", ({ level, message }) => {
    if (level === "warning" || level === "error") sessionLog.append("renderer", message)
  })

  win.on("close", () => saveWindowState(win))

  win.once("ready-to-show", () => {
    if (savedState?.maximized ?? true) {
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

  // The renderer's own matchMedia isn't a reliable single source of truth
  // for the OS theme inside a packaged app (it can lag or diverge from what
  // Chromium/Electron itself resolves), so nativeTheme is authoritative and
  // the renderer only ever mirrors it: a sync read on preload boot for the
  // first paint, then this push on every change.
  ipcMain.on("theme:get-system", (event) => {
    event.returnValue = nativeTheme.shouldUseDarkColors ? "dark" : "light"
  })
  nativeTheme.on("updated", () => {
    const systemTheme = nativeTheme.shouldUseDarkColors ? "dark" : "light"
    for (const win of currentWindows()) {
      win.webContents.send("theme:system-changed", systemTheme)
    }
    if (loadThemePreference() === "system") {
      applyBackgroundColorToAllWindows("system")
    }
  })
  app
    .whenReady()
    .then(async () => {
      applyLocalePreference(loadLocalePreference())
      applyDevAppIdentity()
      const boot = await bootSidecars()
      registerDocumentHandlers(boot.dataDir)
      registerLocaleHandlers({
        isTrusted: (sender) =>
          mainWindow !== null && sender === mainWindow.webContents,
      })
      registerAboutHandlers()
      registerSessionLogHandlers({
        isTrusted: (sender) =>
          mainWindow !== null && sender === mainWindow.webContents,
      })
      installMenu()
      createWindow(boot.apiUrl)
      await registerUpdateHandlers()
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

// Thin, auto-hiding scrollbars on every scroll container; must be set before whenReady().
app.commandLine.appendSwitch(
  "enable-features",
  "OverlayScrollbar,FluentScrollbar,FluentOverlayScrollbars"
)

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
