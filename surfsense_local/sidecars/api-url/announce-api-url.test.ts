import assert from "node:assert/strict"
import { existsSync, mkdtempSync, readFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { announceApiUrl, withdrawApiUrl } from "./announce-api-url.ts"

test("writes the API's address where a plugin author's tools look for it", () => {
  const dataDir = mkdtempSync(join(tmpdir(), "api-url-"))

  announceApiUrl(dataDir, "http://127.0.0.1:5123")

  assert.equal(readFileSync(join(dataDir, "api-url"), "utf8"), "http://127.0.0.1:5123")
})

test("removes it on quit, so nothing points at an app that is gone", () => {
  const dataDir = mkdtempSync(join(tmpdir(), "api-url-"))
  announceApiUrl(dataDir, "http://127.0.0.1:5123")

  withdrawApiUrl(dataDir)

  assert.equal(existsSync(join(dataDir, "api-url")), false)
})

test("removing it when it is already gone is harmless", () => {
  const dataDir = mkdtempSync(join(tmpdir(), "api-url-"))

  assert.doesNotThrow(() => withdrawApiUrl(dataDir))
})
