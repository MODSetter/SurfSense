import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { parsePrivacyFile, privacyStore } from "./privacy-file.ts"

const NOW = new Date("2026-10-21T09:00:00Z")

function inTempFolder(run: (folder: string) => void): void {
  const folder = mkdtempSync(join(tmpdir(), "privacy-file-"))
  try {
    run(folder)
  } finally {
    rmSync(folder, { recursive: true, force: true })
  }
}

test("a new install has never been asked, and its first run is stamped once", () => {
  inTempFolder((folder) => {
    const path = join(folder, "privacy.json")

    const first = privacyStore(path, { now: () => NOW }).read()
    const later = privacyStore(path, { now: () => new Date("2027-01-01T00:00:00Z") }).read()

    assert.deepEqual(first, {
      usageStatistics: null,
      firstRunAt: "2026-10-21T09:00:00.000Z",
      firstRunAsked: false,
      lastReport: null,
      lastSent: null,
      attempts: null,
    })
    assert.equal(later.firstRunAt, "2026-10-21T09:00:00.000Z")
    assert.equal(JSON.parse(readFileSync(path, "utf8")).firstRunAt, first.firstRunAt)
  })
})

test("changes are written through and read back", () => {
  inTempFolder((folder) => {
    const path = join(folder, "privacy.json")
    const store = privacyStore(path, { now: () => NOW })

    store.update((file) => ({ ...file, usageStatistics: true, firstRunAsked: true }))

    const reread = privacyStore(path).read()
    assert.equal(reread.usageStatistics, true)
    assert.equal(reread.firstRunAsked, true)
  })
})

test("junk on disk reads as never set", () => {
  inTempFolder((folder) => {
    const path = join(folder, "privacy.json")
    writeFileSync(path, "{ not json")
    assert.equal(privacyStore(path, { now: () => NOW }).read().usageStatistics, null)
  })
  assert.deepEqual(
    parsePrivacyFile(
      {
        usageStatistics: "yes",
        firstRunAsked: 1,
        lastReport: { day: "today", week: "2026-W43", month: "2026-10" },
        lastSent: { at: "never", body: {} },
        attempts: { day: "2026-10-21", count: "3" },
      },
      NOW
    ),
    {
      usageStatistics: null,
      firstRunAt: "2026-10-21T09:00:00.000Z",
      firstRunAsked: false,
      lastReport: null,
      lastSent: null,
      attempts: null,
    }
  )
})

test("a failed write keeps the choice for this run and is reported, never thrown", () => {
  inTempFolder((folder) => {
    const errors: unknown[] = []
    const store = privacyStore(join(folder, "missing", "privacy.json"), {
      now: () => NOW,
      onWriteError: (error) => errors.push(error),
    })

    store.update((file) => ({ ...file, usageStatistics: false }))

    assert.equal(store.read().usageStatistics, false)
    assert.equal(errors.length, 2)
  })
})
