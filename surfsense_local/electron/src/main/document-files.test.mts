import assert from "node:assert/strict"
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { managedOriginalPath } from "./document-files.mts"

test("resolves a backend-managed original without duplicating its formats", async (t) => {
  const dataDir = await mkdtemp(join(tmpdir(), "surfsense-document-"))
  t.after(() => rm(dataDir, { force: true, recursive: true }))
  const directory = join(dataDir, "data", "workspaces", "2", "documents", "7")
  await mkdir(directory, { recursive: true })
  const original = join(directory, "original.futureformat")
  await writeFile(original, "validated by the backend")

  assert.equal(await managedOriginalPath(dataDir, 2, 7), original)
})

test("rejects invalid identifiers and malformed original names", async (t) => {
  const dataDir = await mkdtemp(join(tmpdir(), "surfsense-document-"))
  t.after(() => rm(dataDir, { force: true, recursive: true }))
  const directory = join(dataDir, "data", "workspaces", "2", "documents", "7")
  await mkdir(directory, { recursive: true })
  await writeFile(join(directory, "original.pdf.exe"), "not a managed original")

  await assert.rejects(() => managedOriginalPath(dataDir, "../2", 7))
  await assert.rejects(
    () => managedOriginalPath(dataDir, 2, 7),
    /no longer available/
  )
})

test("requires exactly one regular original", async (t) => {
  const dataDir = await mkdtemp(join(tmpdir(), "surfsense-document-"))
  t.after(() => rm(dataDir, { force: true, recursive: true }))
  const directory = join(dataDir, "data", "workspaces", "2", "documents", "7")
  await mkdir(directory, { recursive: true })
  await writeFile(join(directory, "original.pdf"), "%PDF-test")
  await writeFile(join(directory, "original.txt"), "unexpected second original")

  await assert.rejects(
    () => managedOriginalPath(dataDir, 2, 7),
    /no longer available/
  )
})
