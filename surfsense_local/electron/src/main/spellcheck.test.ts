import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import { refuseSpellcheckDownloads } from "./spellcheck.ts"

function fakeApp() {
  const listeners: Record<string, ((session: never) => void)[]> = {}
  return {
    listeners,
    on(event: string, listener: (session: never) => void) {
      ;(listeners[event] ??= []).push(listener)
    },
  }
}

test("empties the spellchecker's language list for every session created", () => {
  const app = fakeApp()
  refuseSpellcheckDownloads(app)

  const set: string[][] = []
  const session = {
    setSpellCheckerLanguages: (languages: string[]) => set.push(languages),
  }
  for (const listener of app.listeners["session-created"] ?? []) {
    listener(session as never)
    listener(session as never)
  }

  // A language in the list is what Chromium downloads a dictionary for.
  assert.deepEqual(set, [[], []])
})

test("listens for nothing but a session being created", () => {
  const app = fakeApp()
  refuseSpellcheckDownloads(app)

  assert.deepEqual(Object.keys(app.listeners), ["session-created"])
})

test("is registered before the app can become ready", () => {
  // Measured on Electron 44.2.0: one `await` after `ready` is already too late,
  // because the default session starts its download when it is created.
  const source = readFileSync(new URL("./index.ts", import.meta.url), "utf8")
  const registered = source.indexOf("\nrefuseSpellcheckDownloads(app)")
  const started = source.indexOf("\nif (app.requestSingleInstanceLock())")

  assert.ok(registered !== -1, "index.ts calls it at the top level")
  assert.ok(started !== -1)
  assert.ok(registered < started)
})
