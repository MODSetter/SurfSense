import assert from "node:assert/strict"
import test from "node:test"

import { confineSnapshotSession, type SnapshotSession } from "./confine-snapshot-session.ts"

type Listener = Parameters<SnapshotSession["webRequest"]["onBeforeRequest"]>[0]
type RequestHandler = Parameters<SnapshotSession["setPermissionRequestHandler"]>[0]
type CheckHandler = Parameters<SnapshotSession["setPermissionCheckHandler"]>[0]
type Permission = Parameters<NonNullable<CheckHandler>>[1]

/** A session that records the request filter and answers whether a URL passes it. */
function fakeSession() {
  let listener: Listener | undefined
  let request: RequestHandler = null
  let check: CheckHandler = null
  const session: SnapshotSession = {
    webRequest: {
      onBeforeRequest: (registered) => {
        listener = registered
      },
    },
    setPermissionRequestHandler: (handler) => {
      request = handler
    },
    setPermissionCheckHandler: (handler) => {
      check = handler
    },
  }
  const passes = (url: string): boolean => {
    let cancelled: boolean | undefined
    listener?.({ url }, (response) => {
      cancelled = response.cancel
    })
    assert.notEqual(cancelled, undefined, `no answer for ${url}`)
    return cancelled === false
  }
  /** Whether the page gets a permission, by asking for it or by checking it. */
  const grants = (permission: Permission): boolean => {
    assert.ok(request && check, "no permission handlers were set")
    const frame = { isMainFrame: true, requestingUrl: PACKAGED.href }
    let requested: boolean | undefined
    request(
      {} as Electron.WebContents,
      permission,
      (granted) => {
        requested = granted
      },
      { ...frame, mediaTypes: ["audio"] },
    )
    assert.notEqual(requested, undefined, `no answer for ${permission}`)
    return requested === true || check(null, permission, "file:///", frame)
  }
  return { session, passes, grants }
}

const PACKAGED = new URL("file:///C:/Program%20Files/SurfSense/resources/frontend/dist/docx-snapshot.html")
const DEV = new URL("http://localhost:5173/docx-snapshot.html")
const FILE = "http://127.0.0.1:51234/artifacts/12/files/primary"

test("the packaged page loads its own files and nothing else on disk", () => {
  const { session, passes } = fakeSession()
  confineSnapshotSession(session, PACKAGED)

  assert.ok(passes(PACKAGED.href))
  assert.ok(passes("file:///C:/Program%20Files/SurfSense/resources/frontend/dist/assets/docx-snapshot-a1.js"))
  assert.ok(!passes("file:///C:/Users/me/.surfsense/secret.bin"))
  assert.ok(!passes("file:///C:/Program%20Files/SurfSense/resources/app.asar"))
})

test("the page's own object URLs load, as a deck's pictures are", () => {
  const { session, passes } = fakeSession()
  confineSnapshotSession(session, PACKAGED)

  assert.ok(passes("blob:file:///6d1f4c3a-7b8e-4f0a-9c2d-1e5b7a9c0f11"))
})

test("a page's own data URLs load, as a web page's inline images are", () => {
  const { session, passes } = fakeSession()
  confineSnapshotSession(session, PACKAGED)

  assert.ok(passes("data:image/png;base64,iVBORw0KGgo="))
  assert.ok(!passes("https://example.com/data:image/png"))
})

test("a Word file is reachable only while it is being printed", () => {
  const { session, passes } = fakeSession()
  const allow = confineSnapshotSession(session, PACKAGED)

  assert.ok(!passes(FILE))
  const release = allow(FILE)
  assert.ok(passes(FILE))
  assert.ok(!passes("http://127.0.0.1:51234/artifacts/13/files/primary"))
  assert.ok(!passes("http://127.0.0.1:51234/workspaces"))
  release()
  assert.ok(!passes(FILE))
})

test("two prints of one file keep it reachable until both are done", () => {
  const { session, passes } = fakeSession()
  const allow = confineSnapshotSession(session, PACKAGED)

  const first = allow(FILE)
  const second = allow(FILE)
  first()
  assert.ok(passes(FILE))
  second()
  assert.ok(!passes(FILE))
})

test("in development the page reaches its dev server and nothing else", () => {
  const { session, passes } = fakeSession()
  confineSnapshotSession(session, DEV)

  assert.ok(passes("http://localhost:5173/@vite/client"))
  assert.ok(passes("http://localhost:5173/src/features/docx-snapshot/main.ts"))
  // Vite's client keeps a websocket to its dev server.
  assert.ok(passes("ws://localhost:5173/?token=abc"))
  assert.ok(!passes("ws://localhost:4096/"))
  assert.ok(!passes("http://127.0.0.1:51234/workspaces"))
  assert.ok(!passes("https://example.com/collect"))
  assert.ok(!passes("file:///C:/Users/me/.surfsense/secret.bin"))
})

test("the page is refused every permission, the microphone and the clipboard included", () => {
  const { session, grants } = fakeSession()
  confineSnapshotSession(session, PACKAGED)

  for (const permission of [
    "media",
    "display-capture",
    "clipboard-sanitized-write",
    "clipboard-read",
    "notifications",
    "fullscreen",
  ] as const) {
    assert.ok(!grants(permission), permission)
  }
})
