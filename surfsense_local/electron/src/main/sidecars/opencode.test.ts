import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { CONFIG_FILE, opencodeSpec } from "./opencode.ts"
import { exe } from "./platform.ts"
import type { SidecarContext } from "./types.ts"

/** A staged opencode and an agent folder, with the API's config written or not. */
function staged({ configured = true } = {}): SidecarContext {
  const root = mkdtempSync(join(tmpdir(), "opencode-"))
  const runtime = join(root, "resources", "opencode")
  const agentDir = join(root, "agent")
  mkdirSync(runtime, { recursive: true })
  mkdirSync(agentDir, { recursive: true })
  writeFileSync(join(runtime, exe("opencode")), "")
  if (configured) writeFileSync(join(agentDir, CONFIG_FILE), "{}")
  return {
    packaged: true,
    backendDir: root,
    binariesDir: join(root, "resources"),
    host: "127.0.0.1",
    apiPort: 1,
    dataDir: root,
    secret: "s",
    opencodeBinariesDir: runtime,
    opencodePort: 4321,
    opencodePassword: "launch-password",
    agentDir,
  }
}

test("does not run when the pinned build is not staged", () => {
  const ctx = staged()
  assert.equal(opencodeSpec({ ...ctx, opencodeBinariesDir: join(ctx.dataDir, "absent") }), null)
})

test("waits for the API to write its configuration", () => {
  // The API decides when the agent is first needed; until then nothing runs.
  assert.equal(opencodeSpec(staged({ configured: false })), null)
})

test("serves on loopback, on the port the API was told", () => {
  // Left to itself opencode tries 4096 first, which the API would not know.
  const spec = opencodeSpec(staged())
  assert.ok(spec)
  assert.deepEqual(spec.args, ["serve", "--hostname", "127.0.0.1", "--port", "4321"])
})

test("gets an environment of its own, never Electron's", () => {
  // An inherited OPENCODE_PERMISSION is merged over our rules, and the secret
  // decrypts every stored API key; shell commands inherit whatever opencode has.
  process.env.SURFSENSE_LOCAL_SECRET = "leaked"
  process.env.OPENCODE_PERMISSION = '{"bash":"allow"}'
  try {
    const spec = opencodeSpec(staged())
    assert.ok(spec)
    assert.equal(spec.inheritEnv, false)
    assert.equal(spec.env.SURFSENSE_LOCAL_SECRET, undefined)
    assert.equal(spec.env.OPENCODE_PERMISSION, undefined)
  } finally {
    delete process.env.SURFSENSE_LOCAL_SECRET
    delete process.env.OPENCODE_PERMISSION
  }
})

test("keeps its home, settings and state inside the agent folder", () => {
  const ctx = staged()
  const spec = opencodeSpec(ctx)
  assert.ok(spec)
  const home = join(ctx.agentDir!, "opencode")
  for (const name of ["HOME", "USERPROFILE", "OPENCODE_TEST_HOME"]) {
    assert.equal(spec.env[name], home, name)
  }
  for (const name of ["XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"]) {
    assert.ok(spec.env[name].startsWith(home), name)
  }
  assert.equal(spec.env.OPENCODE_CONFIG, join(ctx.agentDir!, CONFIG_FILE))
})

test("requires the launch password", () => {
  const spec = opencodeSpec(staged())
  assert.ok(spec)
  assert.equal(spec.env.OPENCODE_SERVER_PASSWORD, "launch-password")
})

test("switches off every fetch and sends anything missed nowhere", () => {
  const spec = opencodeSpec(staged())
  assert.ok(spec)
  for (const flag of [
    "OPENCODE_DISABLE_MODELS_FETCH",
    "OPENCODE_DISABLE_SHARE",
    "OPENCODE_DISABLE_LSP_DOWNLOAD",
    "OPENCODE_DISABLE_AUTOUPDATE",
    "OPENCODE_DISABLE_DEFAULT_PLUGINS",
    "OPENCODE_PURE",
    "OPENCODE_DISABLE_PROJECT_CONFIG",
    "OPENCODE_DISABLE_EXTERNAL_SKILLS",
    "OPENCODE_DISABLE_CLAUDE_CODE",
  ]) {
    assert.equal(spec.env[flag], "1", flag)
  }
  for (const proxy of ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]) {
    assert.match(spec.env[proxy], /^http:\/\/127\.0\.0\.1:\d+$/, proxy)
  }
  assert.equal(spec.env.NO_PROXY, "127.0.0.1,localhost,::1")
})

test("finds the ripgrep shipped beside it before any other", () => {
  const ctx = staged()
  const spec = opencodeSpec(ctx)
  assert.ok(spec)
  assert.ok(spec.env.PATH.startsWith(ctx.opencodeBinariesDir!))
})
