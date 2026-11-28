import assert from "node:assert/strict"
import { join } from "node:path"
import test from "node:test"

import { noticesPath, registerNoticesHandlers } from "./notices-ipc.ts"

type Listener = (event: Electron.IpcMainInvokeEvent) => unknown
type Sender = "app" | "app subframe" | "other window"

const FILE = join("/opt/SurfSense/resources", "licenses", "THIRD_PARTY_NOTICES.txt")

/** The main process with the handler registered, over a disk that has the notices or not. */
function mainProcess(options: { present?: boolean; openResult?: string } = {}) {
  const handlers = new Map<string, Listener>()
  const appWindow = { mainFrame: {} } as unknown as Electron.WebContents
  const otherWindow = { mainFrame: {} } as unknown as Electron.WebContents
  const opened: string[] = []

  registerNoticesHandlers({
    ipc: {
      handle: (channel: string, listener: Listener) => {
        handlers.set(channel, listener)
      },
    } as unknown as Pick<Electron.IpcMain, "handle">,
    file: FILE,
    isTrusted: (sender) => sender === appWindow,
    openPath: async (path) => {
      opened.push(path)
      return options.openResult ?? ""
    },
    exists: (path) => path === FILE && (options.present ?? true),
  })

  const open = async (from: Sender = "app") => {
    const listener = handlers.get("about:open-notices")
    assert.ok(listener, "nothing handles about:open-notices")
    const sender = from === "other window" ? otherWindow : appWindow
    const senderFrame = from === "app subframe" ? {} : sender.mainFrame
    return listener({ sender, senderFrame } as unknown as Electron.IpcMainInvokeEvent)
  }

  return { open, opened }
}

test("finds the notices under resources when packaged, and beside the app in dev", () => {
  const app = { appPath: "/src/surfsense_local/electron", resourcesPath: "/opt/SurfSense/resources" }
  assert.equal(
    noticesPath({ ...app, packaged: true }),
    join("/opt/SurfSense/resources", "licenses", "THIRD_PARTY_NOTICES.txt")
  )
  assert.equal(
    noticesPath({ ...app, packaged: false }),
    join("/src/surfsense_local/electron", "licenses", "THIRD_PARTY_NOTICES.txt")
  )
})

test("opens the notices for the app's window", async () => {
  const main = mainProcess()

  assert.equal(await main.open(), "")
  assert.deepEqual(main.opened, [FILE])
})

test("passes on the system's reason when the file cannot be opened", async () => {
  const main = mainProcess({ openResult: "No application is associated with this file" })

  assert.equal(await main.open(), "No application is associated with this file")
})

test("names the missing file rather than asking the system to open it", async () => {
  const main = mainProcess({ present: false })

  assert.equal(await main.open(), `${FILE} does not exist.`)
  assert.deepEqual(main.opened, [])
})

test("opens nothing for another window or a frame inside the app", async () => {
  const main = mainProcess()

  assert.equal(await main.open("other window"), "The request did not come from the application.")
  assert.equal(await main.open("app subframe"), "The request did not come from the application.")
  assert.deepEqual(main.opened, [])
})
