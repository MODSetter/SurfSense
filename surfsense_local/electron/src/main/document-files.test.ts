import assert from "node:assert/strict"
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import test, { type TestContext } from "node:test"

import { managedOriginalPath } from "./document-files.ts"

test("resolves a backend-managed original without duplicating its formats", async (t) => {
  const dataDir = await mkdtemp(join(tmpdir(), "surfsense-document-"))
  t.after(() => rm(dataDir, { force: true, recursive: true }))
  const directory = join(dataDir, "data", "workspaces", "2", "documents", "7")
  await mkdir(directory, { recursive: true })
  const original = join(directory, "original.futureformat")
  await writeFile(original, "validated by the backend")

  assert.equal(await managedOriginalPath(dataDir, 2, 7), original)
})

test("resolves an original stored under its own name", async (t) => {
  const directory = await documentFolder(t)
  const original = join(directory, "Q3 report.pdf")
  await writeFile(original, "%PDF-test")

  assert.equal(await managedOriginalPath(dataDir(directory), 2, 7), original)
})

test("resolves a legacy original beside its extracted text", async (t) => {
  const directory = await documentFolder(t)
  const original = join(directory, "original.pdf")
  await writeFile(original, "%PDF-test")
  await writeFile(join(directory, "extracted.md"), "# parsed")

  assert.equal(await managedOriginalPath(dataDir(directory), 2, 7), original)
})

test("never opens extracted text in place of a deleted original", async (t) => {
  const directory = await documentFolder(t)
  await writeFile(join(directory, "extracted.md"), "# parsed")

  await assert.rejects(
    () => managedOriginalPath(dataDir(directory), 2, 7),
    /no longer available/
  )
})

test("ignores files the operating system leaves in the folder", async (t) => {
  const directory = await documentFolder(t)
  const original = join(directory, "report.pdf")
  await writeFile(original, "%PDF-test")
  await writeFile(join(directory, ".DS_Store"), "")
  await writeFile(join(directory, "Thumbs.db"), "")
  await writeFile(join(directory, "desktop.ini"), "")

  assert.equal(await managedOriginalPath(dataDir(directory), 2, 7), original)
})

test("rejects invalid identifiers", async (t) => {
  const directory = await documentFolder(t)

  await assert.rejects(() => managedOriginalPath(dataDir(directory), "../2", 7))
})

test("requires exactly one original", async (t) => {
  const directory = await documentFolder(t)
  await writeFile(join(directory, "report.pdf"), "%PDF-test")
  await writeFile(join(directory, "notes.txt"), "unexpected second file")

  await assert.rejects(
    () => managedOriginalPath(dataDir(directory), 2, 7),
    /no longer available/
  )
})

async function documentFolder(t: TestContext): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "surfsense-document-"))
  t.after(() => rm(root, { force: true, recursive: true }))
  const directory = join(root, "data", "workspaces", "2", "documents", "7")
  await mkdir(directory, { recursive: true })
  return directory
}

function dataDir(directory: string): string {
  return resolve(directory, "..", "..", "..", "..", "..")
}
