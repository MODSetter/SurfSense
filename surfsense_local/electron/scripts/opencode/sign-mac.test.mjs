import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

/** `mac.signIgnore` in electron-builder.yml, as the regexes electron-builder makes of it. */
function signIgnore() {
  const yml = readFileSync(new URL("../../electron-builder.yml", import.meta.url), "utf8").replace(/\r\n/g, "\n")
  const mac = yml.match(/^mac:\n((?:[ \t]+.*\n|\n)*)/m)?.[1] ?? ""
  const list = mac.match(/^  signIgnore:\n((?:    - .*\n)*)/m)?.[1] ?? ""
  return list
    .split("\n")
    .filter(Boolean)
    .map((line) => new RegExp(line.replace(/^\s*-\s*"?/, "").replace(/"\s*$/, "")))
}

// osx-sign tests each file's absolute path against the filter.
const contents = "/runner/release/mac-arm64/SurfSense.app/Contents"
const skipped = (path) => signIgnore().some((pattern) => pattern.test(path))

test("opencode keeps its vendor's signature, whose entitlements are the ones Bun needs", () => {
  assert.ok(skipped(`${contents}/Resources/opencode/opencode`))
})

test("everything else is still signed with the app, rg included, which arrives ad-hoc signed", () => {
  for (const path of [
    `${contents}/Resources/opencode/rg`,
    `${contents}/MacOS/SurfSense`,
    `${contents}/Resources/llamacpp/llama-server`,
    `${contents}/Resources/backend/api/opencode`,
  ]) {
    assert.ok(!skipped(path), path)
  }
})
