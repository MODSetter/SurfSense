import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { npmNotices } from "./npm.mjs"

test("one entry per installed version, with the text of its licence files", () => {
  const root = mkdtempSync(join(tmpdir(), "npm-notices-"))
  try {
    const a = join(root, "a")
    const b = join(root, "b")
    mkdirSync(a)
    mkdirSync(b)
    writeFileSync(join(a, "LICENSE.md"), "MIT License, version one")
    writeFileSync(join(b, "readme.md"), "no licence here")
    // The shape `pnpm licenses list --json` prints: versions and paths pair up.
    const report = {
      MIT: [{ name: "pkg", versions: ["1.0.0", "2.0.0"], paths: [a, b], license: "MIT" }],
    }
    const entries = npmNotices(report, "frontend")
    assert.deepEqual(
      entries.map(({ name, version, tree, license }) => [name, version, tree, license]),
      [
        ["pkg", "1.0.0", "frontend", "MIT"],
        ["pkg", "2.0.0", "frontend", "MIT"],
      ],
    )
    assert.match(entries[0].text, /version one/)
    assert.equal(entries[1].text, "")
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})
