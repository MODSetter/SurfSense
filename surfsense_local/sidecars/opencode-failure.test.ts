import assert from "node:assert/strict"
import { mkdtempSync, readFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { recordOpencodeFailure } from "./opencode-failure.ts"

test("giving up leaves the reason where the API reads it", () => {
  const agentDir = mkdtempSync(join(tmpdir(), "opencode-failure-"))

  recordOpencodeFailure(agentDir, "opencode exited with code 7")

  const written = JSON.parse(readFileSync(join(agentDir, "opencode-failed.json"), "utf8"))
  assert.deepEqual(written, { reason: "opencode exited with code 7" })
})
