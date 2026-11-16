import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import { installPermissionHandlers } from "./handlers.ts"

type RequestHandler = Parameters<
  Electron.Session["setPermissionRequestHandler"]
>[0]
type CheckHandler = Parameters<Electron.Session["setPermissionCheckHandler"]>[0]
type Permission = Parameters<NonNullable<RequestHandler>>[1]

const PACKAGED = new URL(
  "file:///C:/Program%20Files/SurfSense/resources/frontend/dist/index.html"
)
const DEV = new URL("http://localhost:5173")

type Ask = {
  from?: "main window" | "other window"
  url?: string
  isMainFrame?: boolean
  mediaTypes?: ("audio" | "video")[]
}

/** The app's default session as Electron creates it, with the main window in it. */
function appSession(appPage: URL) {
  const mainWindow = {} as Electron.WebContents
  const otherWindow = {} as Electron.WebContents
  const created: ((session: never) => void)[] = []
  installPermissionHandlers(
    {
      on: (_event: "session-created", listener: (session: never) => void) =>
        created.push(listener),
    },
    { appPage, isMainWindow: (contents) => contents === mainWindow }
  )

  let request: RequestHandler = null
  let check: CheckHandler = null
  const session = {
    setPermissionRequestHandler: (handler: RequestHandler) => {
      request = handler
    },
    setPermissionCheckHandler: (handler: CheckHandler) => {
      check = handler
    },
  }
  for (const listener of created) listener(session as never)

  const contentsOf = (ask: Ask) =>
    ask.from === "other window" ? otherWindow : mainWindow
  const urlOf = (ask: Ask) => ask.url ?? appPage.href

  /** What a page's request gets, as getUserMedia or the Clipboard API asks. */
  const requests = (permission: Permission, ask: Ask = {}): boolean => {
    let granted: boolean | undefined
    assert.ok(request, "no request handler was set")
    request(
      contentsOf(ask),
      permission,
      (answer) => {
        granted = answer
      },
      {
        isMainFrame: ask.isMainFrame ?? true,
        requestingUrl: urlOf(ask),
        mediaTypes: ask.mediaTypes ?? ["audio"],
        securityOrigin: new URL(urlOf(ask)).origin,
      }
    )
    assert.notEqual(granted, undefined, `no answer for ${permission}`)
    return granted === true
  }

  /** What a page's check gets, as the Permissions API or a device list asks. */
  const checks = (
    permission: Permission,
    ask: Omit<Ask, "mediaTypes"> & {
      mediaType?: "audio" | "video" | "unknown"
    } = {}
  ): boolean => {
    assert.ok(check, "no check handler was set")
    return check(contentsOf(ask), permission, new URL(urlOf(ask)).origin, {
      isMainFrame: ask.isMainFrame ?? true,
      requestingUrl: urlOf(ask),
      ...(permission === "media"
        ? { mediaType: ask.mediaType ?? "audio" }
        : {}),
    })
  }

  return { requests, checks }
}

test("the app's own page in the main window may open the microphone", () => {
  assert.ok(appSession(PACKAGED).requests("media"))
  assert.ok(appSession(DEV).requests("media"))
})

test("no camera and no screen: video, audio with video, a desktop capture and display-capture are refused", () => {
  const { requests } = appSession(PACKAGED)

  assert.ok(!requests("media", { mediaTypes: ["video"] }))
  assert.ok(!requests("media", { mediaTypes: ["audio", "video"] }))
  // getUserMedia for a desktop or tab names no device type.
  assert.ok(!requests("media", { mediaTypes: [] }))
  assert.ok(!requests("display-capture"))
})

test("a frame in the page, another window, or another page in the main window gets no microphone", () => {
  const packaged = appSession(PACKAGED)
  assert.ok(!packaged.requests("media", { isMainFrame: false }))
  assert.ok(!packaged.requests("media", { from: "other window" }))
  assert.ok(
    !packaged.requests("media", {
      url: "file:///C:/Users/me/.surfsense/data/workspaces/1/documents/2/page.html",
    })
  )
  assert.ok(
    !packaged.requests("media", {
      url: "file:///C:/Program%20Files/SurfSense/resources/frontend/dist-other/index.html",
    })
  )
  assert.ok(!packaged.requests("media", { url: "https://example.com/" }))
  // The same path on another computer's share is not the app's page.
  assert.ok(
    !packaged.requests("media", {
      url: "file://share.example/C:/Program%20Files/SurfSense/resources/frontend/dist/index.html",
    })
  )
  // An escaped slash is part of a name, not a way into the app's folder.
  assert.ok(
    !packaged.requests("media", {
      url: "file:///C:/Program%20Files/SurfSense/resources/frontend/dist%2F..%2F..%2Fevil.html",
    })
  )

  const dev = appSession(DEV)
  assert.ok(!dev.requests("media", { url: "http://localhost:5174/" }))
  assert.ok(!dev.requests("media", { url: "http://127.0.0.1:8000/" }))
  assert.ok(!dev.requests("media", { url: "file:///C:/Users/me/page.html" }))
})

test("the app's page counts however Chromium spells its path", () => {
  // Chromium escapes `;` where Node does not, and writes the drive letter in capitals.
  const page = new URL(
    "file:///c:/Users/a;b/AppData/Local/Programs/SurfSense/resources/frontend/dist/index.html"
  )
  const { requests } = appSession(page)

  assert.ok(
    requests("media", {
      url: "file:///C:/Users/a%3Bb/AppData/Local/Programs/SurfSense/resources/frontend/dist/index.html#/chat",
    })
  )
})

test("a permission check answers as a request does", () => {
  const { checks } = appSession(PACKAGED)

  assert.ok(checks("media"))
  assert.ok(!checks("media", { mediaType: "video" }))
  assert.ok(!checks("media", { mediaType: "unknown" }))
  assert.ok(!checks("media", { isMainFrame: false }))
  assert.ok(!checks("media", { from: "other window" }))
  assert.ok(!checks("media", { url: "https://example.com/" }))
  assert.ok(!checks("display-capture"))
})

test("every other permission keeps Electron's answer, so copying keeps working", () => {
  const { requests, checks } = appSession(PACKAGED)

  assert.ok(requests("clipboard-sanitized-write"))
  assert.ok(checks("clipboard-sanitized-write"))
  assert.ok(requests("fullscreen"))
  assert.ok(checks("notifications", { from: "other window" }))
  // Electron's default refuses this one check, a synchronous paste.
  assert.ok(!checks("deprecated-sync-clipboard-read"))
})

test("is installed before the app can become ready", () => {
  // As for spellcheck: a session created before its handler would keep Electron's allow-all.
  const source = readFileSync(new URL("../index.ts", import.meta.url), "utf8")
  const installed = source.indexOf("\ninstallPermissionHandlers(app, {")
  const started = source.indexOf("\nif (app.requestSingleInstanceLock())")

  assert.ok(installed !== -1, "index.ts calls it at the top level")
  assert.ok(started !== -1)
  assert.ok(installed < started)
})
