import { join } from "node:path"
import { pathToFileURL } from "node:url"

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
import { printInHiddenWindow } from "./docx-snapshot/print-in-hidden-window.ts"
import { serveDocxSnapshots } from "./docx-snapshot/serve-snapshots.ts"
import { allowedExternalUrl } from "./external-url.ts"
import { loadSecret } from "./secret.ts"
import { bootSidecars, type BootContext } from "./sidecars/boot.ts"
import { stopAll, type Sidecars } from "./sidecars/supervisor.ts"
import type { SidecarContext } from "./sidecars/types.ts"
import { refuseSpellcheckDownloads } from "./spellcheck.ts"
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
import { announceApiUrl, withdrawApiUrl } from "./api-url/announce-api-url.ts"
import { applyLocalePreference } from "./i18n/app-locale.ts"
import { loadLocalePreference } from "./i18n/locale-prefs.ts"
import { registerLocaleHandlers } from "./i18n/locale-ipc.ts"
import { registerAboutHandlers } from "./about/about-ipc.ts"
import { sessionLog } from "./session-log/session-log.ts"
import { warnMain } from "./session-log/main-warn.ts"
import { registerSessionLogHandlers } from "./session-log/session-log-ipc.ts"
import { appMenu } from "./menu/app-menu.ts"
import { helpMenu } from "./menu/help-menu.ts"
import { apiQuitConfirmation } from "./quit/api-quit-confirmation.ts"
import { confirmQuit } from "./quit/confirm-running-replies.ts"

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
// This run's API, once it answers; the quit asks it about running replies.
let apiUrl: string | null = null
// Asked once per quit, whether it began at the menu or at the last window.
let quitConfirmed = false
let confirmingQuit = false
let mainWindow: BrowserWindow | null = null
let shuttingDown = false
let stopDocxSnapshots: (() => void) | null = null
// Boot's watchers; they must stop before the sidecars they would otherwise restart.
let stopSidecarWatchers: (() => void) | null = null

function onSidecarCrash(name: string, code: number | null): void {
  warnMain(sessionLog, `sidecar ${name} crashed (code=${code})`)
  // best-effort: let the renderer show an error instead of hanging
  mainWindow?.webContents.send("sidecar:crashed", {
    name,
    code,
  })
}

// The agent looks at the pages of a Word document or deck it made or was given,
// and only Electron can lay one out (docx-snapshot/). The API has the routes only
// beside an opencode.
function serveWordPreviews(ctx: SidecarContext): void {
  if (ctx.docxSnapshotKey == null) return
  const page = app.isPackaged
    ? pathToFileURL(join(app.getAppPath(), "..", "frontend", "dist", "docx-snapshot.html"))
    : new URL("/docx-snapshot.html", DEV_RENDERER_URL)
  stopDocxSnapshots = serveDocxSnapshots({
    apiUrl: `http://${ctx.host}:${ctx.apiPort}`,
    key: ctx.docxSnapshotKey,
    print: printInHiddenWindow(page),
  })
}

/** What only Electron knows: the paths beside the app, and the keychain secret. */
function bootContext(): BootContext {
  // Linux without a keyring daemon: keep booting on Chromium's built-in key
  // rather than refusing to start; same fallback every Electron app takes.
  if (process.platform === "linux") safeStorage.setUsePlainTextEncryption(true)
  const packaged = app.isPackaged
  const appPath = app.getAppPath()
  const resources = process.resourcesPath
  return {
    packaged,
    // dev: backend sits next to electron/; packaged: frozen binaries in resources/
    backendDir: join(appPath, "..", "backend"),
    binariesDir: resources,
    dataDir: DATA_DIR,
    secret: loadSecret(join(app.getPath("userData"), "secret.bin"), safeStorage),
    // Packaged: bundled embedding, voice, and parser packs. Dev: same staging dir.
    modelsDir: packaged
      ? join(resources, "models")
      : join(appPath, "..", "backend", "models"),
    // The staged llama.cpp build, same bytes either way: `fetch-llamacpp.mjs`
    // writes electron/llamacpp/ and packaging copies that folder verbatim.
    llamacppBinariesDir: packaged
      ? join(resources, "llamacpp")
      : join(appPath, "llamacpp"),
    // The staged audio.cpp build, same bytes either way, as for llama.cpp.
    audioBinariesDir: packaged
      ? join(resources, "audiocpp")
      : join(appPath, "audiocpp"),
    // Same staging in both modes, like llama.cpp.
    sdcppBinariesDir: packaged ? join(resources, "sdcpp") : join(appPath, "sdcpp"),
    opencodeBinariesDir: packaged
      ? join(resources, "opencode")
      : join(appPath, "opencode"),
  }
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
    // A hidden Word snapshot window is not the app's; it must not keep the app running.
    app.quit()
  })
  // Its info level is React's and Vite's development chatter.
  win.webContents.on("console-message", ({ level, message }) => {
    if (level === "warning" || level === "error") sessionLog.append("renderer", message)
  })

  win.on("close", (event) => {
    saveWindowState(win)
    // Closing the last window quits the app, so it asks as a quit does.
    if (quitConfirmed || shuttingDown || BrowserWindow.getAllWindows().length > 1)
      return
    event.preventDefault()
    void quitWithConfirmation().then((quit) => {
      if (quit) win.close()
    })
  })

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

/** Whether to quit: asks, and saves, only while replies are being written. */
async function quitWithConfirmation(): Promise<boolean> {
  if (quitConfirmed || apiUrl === null) return true
  if (confirmingQuit) return false
  confirmingQuit = true
  try {
    quitConfirmed = await confirmQuit(
      apiQuitConfirmation(apiUrl, () => mainWindow)
    )
    return quitConfirmed
  } finally {
    confirmingQuit = false
  }
}

async function shutdown(): Promise<void> {
  if (shuttingDown) return
  shuttingDown = true
  stopSidecarWatchers?.()
  stopDocxSnapshots?.()
  withdrawApiUrl(DATA_DIR)
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
      const boot = await bootSidecars(bootContext(), onSidecarCrash)
      apiUrl = boot.apiUrl
      sidecars = boot.sidecars
      stopSidecarWatchers = boot.stopWatching
      serveWordPreviews(boot.ctx)
      await boot.waitHealthy()
      announceApiUrl(boot.dataDir, boot.apiUrl)
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
        if (mainWindow === null) createWindow(boot.apiUrl)
      })
    })
    .catch((err: unknown) => {
      warnMain(sessionLog, `failed to start: ${String(err)}`)
      void shutdown().finally(() => app.exit(1))
    })

  app.on("window-all-closed", () => app.quit())

  // the single choke point that guarantees the sidecars die with the app
  app.on("before-quit", (event) => {
    if (!sidecars || shuttingDown) return
    event.preventDefault()
    void quitWithConfirmation().then((quit) => {
      if (quit) void shutdown().finally(() => app.quit())
    })
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

// Also before whenReady(): the default session is created with the app.
refuseSpellcheckDownloads(app)

// one app, one set of sidecars: a second instance would fight over the SQLite
// file and the port, so hand off to the primary window and quit
if (app.requestSingleInstanceLock()) {
  app.on("second-instance", () => {
    // Not getAllWindows()[0]: that is the newest, which may be a hidden Word snapshot window.
    if (!mainWindow) return
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  })
  main()
} else {
  app.quit()
}
