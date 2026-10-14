import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { createRequire } from "node:module"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import afterSign from "./after-sign.mjs"

const ELECTRON = fileURLToPath(new URL("../..", import.meta.url))

/** What electron-builder hands the hook: the packager places resources under appOutDir. */
function context(t) {
  const appOutDir = mkdtempSync(join(tmpdir(), "surfsense-after-sign-"))
  t.after(() => rmSync(appOutDir, { recursive: true, force: true }))
  return { appOutDir, packager: { getResourcesDir: (out) => join(out, "resources") } }
}

/** The top-level `afterSign` in electron-builder.yml. */
function configuredHook() {
  const yml = readFileSync(join(ELECTRON, "electron-builder.yml"), "utf8")
  return yml.match(/^afterSign:[ \t]*(\S+)/m)?.[1] ?? null
}

test("a signed app whose opencode will not run stops electron-builder before any installer is made", async (t) => {
  const ctx = context(t)
  await assert.rejects(afterSign(ctx), (error) => error.message.startsWith(join(ctx.appOutDir, "resources", "opencode")))
})

test("a build made with opencode off is not checked, since it carries none", async (t) => {
  const before = process.env.SURFSENSE_LOCAL_OPENCODE_ENABLED
  process.env.SURFSENSE_LOCAL_OPENCODE_ENABLED = "0"
  t.after(() => {
    if (before === undefined) delete process.env.SURFSENSE_LOCAL_OPENCODE_ENABLED
    else process.env.SURFSENSE_LOCAL_OPENCODE_ENABLED = before
  })
  await afterSign(context(t))
})

test("electron-builder.yml runs it after signing, and electron-builder loads it as the hook", async () => {
  const hook = configuredHook()
  assert.equal(hook, "./scripts/opencode/after-sign.mjs")
  // Loaded the way electron-builder loads a hook named by path.
  const builder = createRequire(createRequire(import.meta.url).resolve("electron-builder"))
  const { resolveFunction } = builder("app-builder-lib/out/util/resolve")
  assert.equal(await resolveFunction("module", join(ELECTRON, hook), "afterSign", ELECTRON), afterSign)
})
