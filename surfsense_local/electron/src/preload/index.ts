import { contextBridge, ipcRenderer } from "electron"

import type { MicrophoneAccess } from "../main/microphone/system-access.ts"
import type { PrivacyState } from "../main/privacy-choices/privacy-controller.ts"

// main passes the API base URL via additionalArguments; read it back off argv
const FLAG = "--surfsense-api-url="
const arg = process.argv.find((a) => a.startsWith(FLAG))

// nativeTheme (main process) is the single source of truth for the OS theme.
// A sync IPC read here means the value is already correct by the time the
// page's own first-paint script runs, and the "updated" push keeps it live.
let systemTheme = ipcRenderer.sendSync("theme:get-system") as "dark" | "light"
ipcRenderer.on("theme:system-changed", (_event, theme: unknown) => {
  if (theme === "dark" || theme === "light") systemTheme = theme
})

// main owns the interface language; the sync read gives the page its language
// before first paint, and "locale:changed" keeps it live.
let locale = ipcRenderer.sendSync("locale:get") as string
ipcRenderer.on("locale:changed", (_event, next: unknown) => {
  if (typeof next === "string") locale = next
})

type SidecarCrash = { name: string; code: number | null }

function isSidecarCrash(value: unknown): value is SidecarCrash {
  if (typeof value !== "object" || value === null) return false
  const crash = value as Record<string, unknown>
  return (
    typeof crash.name === "string" &&
    (typeof crash.code === "number" || crash.code === null)
  )
}

// the renderer talks HTTP to this base and never sees Node or the sidecars
contextBridge.exposeInMainWorld("surfsense", {
  apiUrl: arg ? arg.slice(FLAG.length) : "http://127.0.0.1:8000",
  platform: process.platform,
  openDocument: (workspaceId: number, documentId: number): Promise<string> =>
    ipcRenderer.invoke("documents:open", workspaceId, documentId),
  revealDocument: (workspaceId: number, documentId: number): Promise<string> =>
    ipcRenderer.invoke("documents:reveal", workspaceId, documentId),
  updates: {
    prefs: () => ipcRenderer.invoke("updates:prefs"),
    setAutomatic: (automatic: boolean) =>
      ipcRenderer.invoke("updates:set-automatic", automatic),
    state: () => ipcRenderer.invoke("updates:state"),
    check: () => ipcRenderer.invoke("updates:check"),
    install: () => ipcRenderer.invoke("updates:install"),
    onState: (listener: (state: unknown) => void) => {
      const wrapped = (_event: unknown, state: unknown) => listener(state)
      ipcRenderer.on("updates:state", wrapped)
      return () => ipcRenderer.removeListener("updates:state", wrapped)
    },
    onCheckRequested: (listener: () => void) => {
      const wrapped = () => listener()
      ipcRenderer.on("updates:check-requested", wrapped)
      return () =>
        ipcRenderer.removeListener("updates:check-requested", wrapped)
    },
  },
  // Update checks and usage statistics: what each sends, where, and the switches
  // (contract 05, part C). State is null outside the app's own window.
  privacy: {
    getState: (): Promise<PrivacyState | null> =>
      ipcRenderer.invoke("privacy:state"),
    setUsageStatistics: async (enabled: boolean): Promise<void> => {
      await ipcRenderer.invoke("privacy:set-usage-statistics", enabled)
    },
    // The updates bridge's own switch, so both bridges stay one setting.
    setUpdatesAutomatic: async (enabled: boolean): Promise<void> => {
      await ipcRenderer.invoke("updates:set-automatic", enabled)
    },
    // The exact next report, built but not sent.
    previewUsageReport: (): Promise<unknown> =>
      ipcRenderer.invoke("privacy:preview-usage-report"),
    completeFirstRun: async (choices: {
      updates: boolean
      usageStatistics: boolean
    }): Promise<void> => {
      await ipcRenderer.invoke("privacy:complete-first-run", choices)
    },
    onStateChanged: (
      listener: (state: PrivacyState) => void
    ): (() => void) => {
      const wrapped = (_event: unknown, state: PrivacyState) => listener(state)
      ipcRenderer.on("privacy:state-changed", wrapped)
      return () => ipcRenderer.removeListener("privacy:state-changed", wrapped)
    },
  },
  setTitleBarOverlay: (overlay: {
    color: string
    symbolColor: string
  }): Promise<void> => ipcRenderer.invoke("shell:titlebar-overlay", overlay),
  openExternal: (url: string): Promise<void> =>
    ipcRenderer.invoke("shell:open-external", url),
  // A content link the user confirmed in the link popup: any https page.
  openConfirmedLink: (url: string): Promise<void> =>
    ipcRenderer.invoke("shell:open-confirmed-link", url),
  // A listed plugin's homepage or privacy policy, named by its id.
  openPluginPage: (
    pluginId: string,
    page: "homepage" | "privacy_policy"
  ): Promise<void> =>
    ipcRenderer.invoke("shell:open-plugin-page", pluginId, page),
  about: {
    details: () => ipcRenderer.invoke("about:details"),
    // Where models, workspaces and settings live; null outside the app's window.
    dataFolder: (): Promise<string | null> =>
      ipcRenderer.invoke("about:data-folder"),
    // "" once opened, else the OS's reason.
    openDataFolder: (): Promise<string> =>
      ipcRenderer.invoke("about:open-data-folder"),
  },
  sessionLog: {
    read: (): Promise<string[]> => ipcRenderer.invoke("session-log:read"),
  },
  // The system's switch for SurfSense's microphone; the page's own permission is main's.
  microphone: {
    status: (): Promise<MicrophoneAccess> =>
      ipcRenderer.invoke("microphone:status"),
    // macOS shows its prompt the first time; call it before getUserMedia.
    request: (): Promise<MicrophoneAccess> =>
      ipcRenderer.invoke("microphone:request"),
    openSettings: (): Promise<boolean> =>
      ipcRenderer.invoke("microphone:open-settings"),
  },
  sidecars: {
    onCrash: (listener: (crash: SidecarCrash) => void): (() => void) => {
      const wrapped = (_event: unknown, crash: unknown) => {
        if (isSidecarCrash(crash)) listener(crash)
      }
      ipcRenderer.on("sidecar:crashed", wrapped)
      return () => ipcRenderer.removeListener("sidecar:crashed", wrapped)
    },
  },
  help: {
    onReportIssue: (listener: () => void): (() => void) => {
      const wrapped = () => listener()
      ipcRenderer.on("help:report-issue", wrapped)
      return () => ipcRenderer.removeListener("help:report-issue", wrapped)
    },
  },
  locale: {
    get: (): string => locale,
    preference: (): Promise<string> => ipcRenderer.invoke("locale:preference"),
    set: (preference: string): Promise<void> =>
      ipcRenderer.invoke("locale:set", preference),
    onChange: (listener: (locale: string) => void): (() => void) => {
      const wrapped = (_event: unknown, next: unknown) => {
        if (typeof next === "string") listener(next)
      }
      ipcRenderer.on("locale:changed", wrapped)
      return () => ipcRenderer.removeListener("locale:changed", wrapped)
    },
  },
  theme: {
    set: (theme: "dark" | "light" | "system"): Promise<void> =>
      ipcRenderer.invoke("theme:set", theme),
    getSystemTheme: (): "dark" | "light" => systemTheme,
    onSystemThemeChange: (
      listener: (theme: "dark" | "light") => void
    ): (() => void) => {
      const wrapped = (_event: unknown, theme: unknown) => {
        if (theme === "dark" || theme === "light") listener(theme)
      }
      ipcRenderer.on("theme:system-changed", wrapped)
      return () => ipcRenderer.removeListener("theme:system-changed", wrapped)
    },
  },
})
