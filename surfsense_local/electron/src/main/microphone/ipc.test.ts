import assert from "node:assert/strict"
import test from "node:test"

import { registerMicrophoneHandlers } from "./ipc.ts"
import type { MicrophoneAccess } from "./system-access.ts"

type Listener = (
  event: Electron.IpcMainInvokeEvent,
  ...args: unknown[]
) => unknown
type Sender = "app" | "app subframe" | "other window"

/** The main process with the handlers registered, on a system whose switch is `access`. */
function mainProcess(
  platform: NodeJS.Platform,
  access: MicrophoneAccess = "granted",
  options: { answer?: MicrophoneAccess; openFails?: boolean } = {}
) {
  const handlers = new Map<string, Listener>()
  const mainFrame = {}
  const appWindow = { mainFrame } as unknown as Electron.WebContents
  const otherWindow = { mainFrame: {} } as unknown as Electron.WebContents
  const asked: string[] = []
  const opened: string[] = []
  let status = access

  registerMicrophoneHandlers({
    ipc: {
      handle: (channel: string, listener: Listener) => {
        handlers.set(channel, listener)
      },
    } as unknown as Pick<Electron.IpcMain, "handle">,
    isTrusted: (sender) => sender === appWindow,
    system: {
      platform,
      preferences: {
        // Electron has neither call on Linux, and asks only on macOS.
        getMediaAccessStatus: () => {
          if (platform === "linux") throw new TypeError("not a function")
          return status
        },
        askForMediaAccess: async (type) => {
          if (platform !== "darwin") throw new TypeError("not a function")
          asked.push(type)
          status = options.answer ?? status
          return status === "granted"
        },
      },
      openExternal: async (url) => {
        if (options.openFails)
          throw new Error("no application handles this link")
        opened.push(url)
      },
    },
  })

  const invoke = async (channel: string, from: Sender = "app") => {
    const listener = handlers.get(channel)
    assert.ok(listener, `nothing handles ${channel}`)
    const sender = from === "other window" ? otherWindow : appWindow
    const senderFrame = from === "app subframe" ? {} : sender.mainFrame
    return listener({
      sender,
      senderFrame,
    } as unknown as Electron.IpcMainInvokeEvent)
  }

  return { invoke, asked, opened }
}

test("reports the system's microphone switch for SurfSense on Windows and macOS", async () => {
  assert.equal(
    await mainProcess("win32", "denied").invoke("microphone:status"),
    "denied"
  )
  assert.equal(
    await mainProcess("win32", "granted").invoke("microphone:status"),
    "granted"
  )
  assert.equal(
    await mainProcess("darwin", "not-determined").invoke("microphone:status"),
    "not-determined"
  )
})

test("on macOS, asks the system before the page opens the microphone, and reports the answer", async () => {
  const mac = mainProcess("darwin", "not-determined", { answer: "granted" })

  assert.equal(await mac.invoke("microphone:request"), "granted")
  assert.deepEqual(mac.asked, ["microphone"])

  const refused = mainProcess("darwin", "not-determined", { answer: "denied" })
  assert.equal(await refused.invoke("microphone:request"), "denied")
})

test("Windows has no prompt for a desktop app, so a request reports the switch as it is", async () => {
  const windows = mainProcess("win32", "denied")

  assert.equal(await windows.invoke("microphone:request"), "denied")
  assert.deepEqual(windows.asked, [])
})

test("Linux has no switch for a desktop app, so the system never stops the microphone there", async () => {
  const linux = mainProcess("linux")

  assert.equal(await linux.invoke("microphone:status"), "granted")
  assert.equal(await linux.invoke("microphone:request"), "granted")
  assert.deepEqual(linux.asked, [])
})

test("opens the system's own microphone settings on Windows and macOS", async () => {
  const windows = mainProcess("win32", "denied")
  assert.equal(await windows.invoke("microphone:open-settings"), true)
  assert.deepEqual(windows.opened, ["ms-settings:privacy-microphone"])

  const mac = mainProcess("darwin", "denied")
  assert.equal(await mac.invoke("microphone:open-settings"), true)
  assert.deepEqual(mac.opened, [
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
  ])

  const linux = mainProcess("linux")
  assert.equal(await linux.invoke("microphone:open-settings"), false)
  assert.deepEqual(linux.opened, [])

  const failing = mainProcess("win32", "denied", { openFails: true })
  assert.equal(await failing.invoke("microphone:open-settings"), false)
})

test("answers only the app's own window, in its main frame", async () => {
  for (const from of ["other window", "app subframe"] as const) {
    const mac = mainProcess("darwin", "not-determined", { answer: "granted" })

    assert.equal(await mac.invoke("microphone:status", from), "denied", from)
    assert.equal(await mac.invoke("microphone:request", from), "denied", from)
    assert.equal(
      await mac.invoke("microphone:open-settings", from),
      false,
      from
    )
    assert.deepEqual(mac.asked, [], from)
    assert.deepEqual(mac.opened, [], from)
  }
})
