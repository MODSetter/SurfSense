import assert from "node:assert/strict"
import { existsSync, mkdirSync, mkdtempSync, readdirSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { opencodeFolders, prepareOpencodeHome } from "./opencode-home.ts"

function agentFolder(): string {
  return mkdtempSync(join(tmpdir(), "opencode-home-"))
}

test("makes every folder opencode's environment names", () => {
  const agentDir = agentFolder()
  prepareOpencodeHome(agentDir)
  for (const [name, folder] of Object.entries(opencodeFolders(agentDir))) {
    assert.ok(existsSync(folder), name)
  }
})

test("leaves no npm stub: 2.x installs nothing at startup", () => {
  const agentDir = agentFolder()
  prepareOpencodeHome(agentDir)
  const config = join(opencodeFolders(agentDir).config, "opencode")
  assert.equal(existsSync(join(config, "package-lock.json")), false)
  assert.equal(existsSync(join(config, "node_modules")), false)
})

test("clears what the last run left in its temp folder", () => {
  // Bun extracts 5.6 MB there at every start and never removes it.
  const agentDir = agentFolder()
  const { temp } = opencodeFolders(agentDir)
  mkdirSync(join(temp, "opencode"), { recursive: true })
  writeFileSync(join(temp, ".bun-1a2b3c.dll"), "")
  writeFileSync(join(temp, "opencode", "scratch.txt"), "")

  prepareOpencodeHome(agentDir)

  assert.deepEqual(readdirSync(temp), [])
})
