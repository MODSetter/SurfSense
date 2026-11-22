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
    opencodePassword: "launch-password", // pragma: allowlist secret
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
  process.env.SURFSENSE_LOCAL_SECRET = "leaked" // pragma: allowlist secret
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
  assert.equal(spec.env.OPENCODE_PASSWORD, "launch-password")
})

test("switches off every fetch and sends anything missed nowhere", () => {
  const spec = opencodeSpec(staged())
  assert.ok(spec)
  // The rest of 1.x's switches are not read by 2.x; its configuration turns those off.
  for (const flag of [
    "OPENCODE_DISABLE_MODELS_FETCH",
    "OPENCODE_DISABLE_CLAUDE_CODE",
    "OPENCODE_CONFIG_PROJECT_DISABLE",
  ]) {
    assert.equal(spec.env[flag], "1", flag)
  }
  for (const proxy of ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]) {
    assert.match(spec.env[proxy], /^http:\/\/127\.0\.0\.1:\d+$/, proxy)
  }
  assert.equal(spec.env.NO_PROXY, "127.0.0.1,localhost,::1")
})

test("reaches the network only through the API's proxy", () => {
  // The API refuses every host there; plugins are reached through its gateway on loopback.
  const spec = opencodeSpec({ ...staged(), opencodeProxyPort: 5555 })
  assert.ok(spec)
  for (const proxy of ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "https_proxy"]) {
    assert.equal(spec.env[proxy], "http://127.0.0.1:5555", proxy)
  }
  assert.equal(spec.env.NO_PROXY, "127.0.0.1,localhost,::1")
})

test("keeps its scratch folder inside the agent folder", () => {
  // opencode's is $TMPDIR/opencode, which the user's own opencode shares.
  const ctx = staged()
  const spec = opencodeSpec(ctx)
  assert.ok(spec)
  for (const name of ["TMPDIR", "TEMP", "TMP"]) {
    assert.ok(spec.env[name].startsWith(join(ctx.agentDir!, "opencode")), name)
  }
})

test(
  "spells the agent folder one way on Windows",
  { skip: process.platform !== "win32" && "Windows paths only" },
  () => {
    // 2.x keeps `c:\` and `C:\`, or a trailing `\`, as separate locations and sessions.
    const ctx = staged()
    const agentDir = ctx.agentDir!
    const respelled = `${agentDir[0].toLowerCase()}${agentDir.slice(1)}\\`
    const spec = opencodeSpec({ ...ctx, agentDir: respelled })
    assert.ok(spec)
    assert.equal(spec.cwd, join(agentDir, "opencode"))
    assert.equal(spec.env.OPENCODE_CONFIG, join(agentDir, CONFIG_FILE))
  }
)

test("finds the ripgrep shipped beside it before any other", () => {
  const ctx = staged()
  const spec = opencodeSpec(ctx)
  assert.ok(spec)
  assert.ok(spec.env.PATH.startsWith(ctx.opencodeBinariesDir!))
})
