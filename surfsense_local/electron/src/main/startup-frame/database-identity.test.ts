import assert from "node:assert/strict"
import { mkdtempSync, renameSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { databaseIdentity } from "./database-identity.ts"

function dataFolder(): string {
  return mkdtempSync(join(tmpdir(), "surfsense-identity-"))
}

test("is absent before the database exists", () => {
  assert.equal(databaseIdentity(dataFolder()), null)
})

test("stays the same for the same database", () => {
  const dir = dataFolder()
  writeFileSync(join(dir, "surfsense.db"), "")
  const first = databaseIdentity(dir)
  assert.equal(typeof first, "string")
  writeFileSync(join(dir, "surfsense.db"), "written to since")
  assert.equal(databaseIdentity(dir), first)
})

test("changes once the database is deleted and made again", () => {
  const dir = dataFolder()
  const path = join(dir, "surfsense.db")
  writeFileSync(path, "")
  const before = databaseIdentity(dir)
  // Made before the old one goes, so the filesystem cannot hand back its inode.
  writeFileSync(`${path}.new`, "")
  rmSync(path)
  renameSync(`${path}.new`, path)
  assert.notEqual(databaseIdentity(dir), before)
})

test("does not reveal where the data folder is", () => {
  const dir = dataFolder()
  writeFileSync(join(dir, "surfsense.db"), "")
  assert.match(databaseIdentity(dir) ?? "", /^[0-9a-f]{32}$/)
})
