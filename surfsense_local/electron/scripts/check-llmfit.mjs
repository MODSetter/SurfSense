// Runnable staging/final-resource smoke: version pin plus real hardware JSON.
import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { existsSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { VERSION, checkConfiguration } from "./fetch-llmfit.mjs"

checkConfiguration()

const here = fileURLToPath(new URL(".", import.meta.url))
const binary =
  process.argv[2] ??
  join(here, "..", "llmfit", process.platform === "win32" ? "llmfit.exe" : "llmfit")

assert.ok(existsSync(binary), `llmfit binary not found: ${binary}`)

const run = (args) =>
  execFileSync(binary, args, {
    encoding: "utf8",
    timeout: 30_000,
    windowsHide: true,
  }).trim()

const version = run(["--version"])
assert.match(version, new RegExp(`\\b${VERSION.replaceAll(".", "\\.")}\\b`))

const system = JSON.parse(run(["--json", "system"]))
assert.ok(system && typeof system === "object", "llmfit system output must be a JSON object")
console.log(`llmfit ${VERSION} smoke OK: ${binary}`)
