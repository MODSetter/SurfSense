import assert from "node:assert/strict"
import test from "node:test"

import { confineSnapshotSession, type SnapshotSession } from "./confine-snapshot-session.ts"

type Listener = Parameters<SnapshotSession["webRequest"]["onBeforeRequest"]>[0]

/** A session that records the request filter and answers whether a URL passes it. */
function fakeSession() {
  let listener: Listener | undefined
  const session: SnapshotSession = {
    webRequest: {
      onBeforeRequest: (registered) => {
        listener = registered
      },
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
  return { session, passes }
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
