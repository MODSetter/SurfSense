import { contextBridge, ipcRenderer } from "electron"

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
  },
  setTitleBarOverlay: (overlay: {
    color: string
    symbolColor: string
  }): Promise<void> => ipcRenderer.invoke("shell:titlebar-overlay", overlay),
  openExternal: (url: string): Promise<void> =>
    ipcRenderer.invoke("shell:open-external", url),
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
