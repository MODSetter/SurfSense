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
      onboardingReported: null,
      hardwareSent: null,
      setupTries: null,
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
        onboardingReported: "unknown",
        hardwareSent: { gpu: 1, vram_gb: "8-11" },
        setupTries: { step: "unknown", at: NOW.toISOString(), count: 1 },
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
      onboardingReported: null,
      hardwareSent: null,
      setupTries: null,
    }
  )
  for (const setupTries of [
    { step: "model_chosen", at: "never", count: 1 },
    { step: "model_chosen", at: NOW.toISOString(), count: "1" },
  ]) {
    assert.equal(parsePrivacyFile({ setupTries }, NOW).setupTries, null)
  }
})

test("the setup report's tries are kept", () => {
  const setupTries = { step: "model_ready", at: NOW.toISOString(), count: 2 }
  assert.deepEqual(parsePrivacyFile({ setupTries }, NOW).setupTries, setupTries)
})

test("what the reports carried is kept, and a file from before it was kept reads it from the last report", () => {
  const sentBody = {
    schema: 1,
    hardware: { ram_gb: "16-31", gpu: "nvidia", vram_gb: "8-11" },
    week: { chat_turns: "0", onboarding: "model_ready" },
  }
  const older = parsePrivacyFile(
    { firstRunAt: NOW.toISOString(), lastSent: { at: NOW.toISOString(), body: sentBody } },
    NOW
  )
  assert.equal(older.onboardingReported, "model_ready")
  // Sent before gpu_runtime existed, so nothing says whether the runtime reaches the card.
  assert.deepEqual(older.hardwareSent, { gpu: "nvidia", vram_gb: "8-11", gpu_runtime: null })

  const kept = parsePrivacyFile(
    {
      lastSent: { at: NOW.toISOString(), body: { ...sentBody, hardware: null, week: null } },
      onboardingReported: "first_answer",
      hardwareSent: { gpu: "amd", vram_gb: "unknown", gpu_runtime: "unreachable" },
    },
    NOW
  )
  assert.equal(kept.onboardingReported, "first_answer")
  assert.deepEqual(kept.hardwareSent, { gpu: "amd", vram_gb: "unknown", gpu_runtime: "unreachable" })
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
