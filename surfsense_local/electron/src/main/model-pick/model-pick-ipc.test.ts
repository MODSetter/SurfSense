import assert from "node:assert/strict"
import test from "node:test"

import { registerModelPickHandlers } from "./model-pick-ipc.ts"

type Listener = (event: Electron.IpcMainInvokeEvent, ...args: unknown[]) => unknown
type Sender = "app" | "app subframe" | "other window"

/** Main with the picker registered, a stand-in for the system dialog, and what it was asked. */
function mainProcess(answer: { canceled: boolean; filePaths: string[] }) {
  const handlers = new Map<string, Listener>()
  const mainFrame = {}
  const appWindow = { mainFrame } as unknown as Electron.WebContents
  const otherWindow = { mainFrame: {} } as unknown as Electron.WebContents
  const asked: Electron.OpenDialogOptions[] = []
  registerModelPickHandlers({
    ipc: {
      handle: (channel: string, listener: Listener) => handlers.set(channel, listener),
    } as unknown as Pick<Electron.IpcMain, "handle">,
    isTrusted: (sender) => sender === appWindow,
    mainWindow: () => ({}) as Electron.BrowserWindow,
    showOpenDialog: async (_window, options) => {
      asked.push(options)
      return answer
    },
  })
  const invoke = (from: Sender, ...args: unknown[]) => {
    const listener = handlers.get("models:pick")
    assert.ok(listener, "no handler for models:pick")
    const sender = from === "other window" ? otherWindow : appWindow
    const senderFrame = from === "app" ? mainFrame : {}
    return listener({ sender, senderFrame } as unknown as Electron.IpcMainInvokeEvent, ...args)
  }
  return { invoke, asked }
}

test("a file pick opens the system dialog on GGUF files and hands back the chosen path", async () => {
  const main = mainProcess({ canceled: false, filePaths: ["/home/ana/models/qwen3-8b.gguf"] })

  assert.equal(await main.invoke("app", "file"), "/home/ana/models/qwen3-8b.gguf")
  const [options] = main.asked
  assert.deepEqual(options?.properties, ["openFile", "dontAddToRecent"])
  assert.deepEqual(options?.filters?.[0]?.extensions, ["gguf"])
})

test("a folder pick asks for a folder", async () => {
  const main = mainProcess({ canceled: false, filePaths: ["D:\\AI\\models"] })

  assert.equal(await main.invoke("app", "folder"), "D:\\AI\\models")
  assert.deepEqual(main.asked[0]?.properties, ["openDirectory", "dontAddToRecent"])
})

test("a dialog closed without a choice hands back nothing", async () => {
  const main = mainProcess({ canceled: true, filePaths: [] })

  assert.equal(await main.invoke("app", "file"), null)
})

test("only the app's own page opens the dialog, and only for a kind it names", async () => {
  const main = mainProcess({ canceled: false, filePaths: ["/x.gguf"] })

  assert.equal(await main.invoke("other window", "file"), null)
  assert.equal(await main.invoke("app subframe", "file"), null)
  assert.equal(await main.invoke("app", "/etc/passwd"), null)
  assert.equal(main.asked.length, 0)
})
