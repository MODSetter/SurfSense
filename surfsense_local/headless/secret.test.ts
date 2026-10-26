import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test, type TestContext } from "node:test"

import { resolveSecret } from "./secret.ts"

function dataDir(t: TestContext): string {
  const dir = mkdtempSync(join(tmpdir(), "surfsense-headless-secret-"))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  return dir
}

test("SURFSENSE_LOCAL_SECRET wins, and nothing is written", (t) => {
  const dir = dataDir(t)
  assert.equal(resolveSecret({ SURFSENSE_LOCAL_SECRET: "from-the-env" }, dir), "from-the-env") // pragma: allowlist secret
  assert.throws(() => statSync(join(dir, "secret")))
})

test("a fresh volume gets one secret, kept private, and the same one ever after", (t) => {
  const dir = join(dataDir(t), "not-yet-made")
  const first = resolveSecret({}, dir)
  assert.match(first, /^[0-9a-f]{64}$/)
  // Windows keeps no POSIX modes; the container is Linux.
  if (process.platform !== "win32") assert.equal(statSync(join(dir, "secret")).mode & 0o777, 0o600)
  assert.equal(resolveSecret({}, dir), first)
  assert.equal(readFileSync(join(dir, "secret"), "utf8").trim(), first)
})

test("a secret already on the volume is kept, as the backend reads it", (t) => {
  const dir = dataDir(t)
  writeFileSync(join(dir, "secret"), "written-before\n")
  assert.equal(resolveSecret({ SURFSENSE_LOCAL_SECRET: "" }, dir), "written-before")
})

test("an empty secret file is refused, since replacing it would lose every stored key", (t) => {
  const dir = dataDir(t)
  writeFileSync(join(dir, "secret"), "  \n")
  assert.throws(() => resolveSecret({}, dir), /secret/)
})
