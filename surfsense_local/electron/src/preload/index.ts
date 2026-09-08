import { contextBridge, ipcRenderer } from "electron"

// main passes the API base URL via additionalArguments; read it back off argv
const FLAG = "--surfsense-api-url="
const arg = process.argv.find((a) => a.startsWith(FLAG))

// the renderer talks HTTP to this base and never sees Node or the sidecars
contextBridge.exposeInMainWorld("surfsense", {
  apiUrl: arg ? arg.slice(FLAG.length) : "http://127.0.0.1:8000",
  platform: process.platform,
  openDocument: (workspaceId: number, documentId: number): Promise<string> =>
    ipcRenderer.invoke("documents:open", workspaceId, documentId),
  revealDocument: (workspaceId: number, documentId: number): Promise<string> =>
    ipcRenderer.invoke("documents:reveal", workspaceId, documentId),
})
