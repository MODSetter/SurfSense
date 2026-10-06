import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { audiocppSpec, SERVER_CONFIG } from "./audiocpp.ts"
import { exe, isWindows } from "./platform.ts"
import { apiSpec, workerSpec } from "./python.ts"
import type { SidecarContext } from "./types.ts"

/** A packaged build with audio.cpp staged and the API's config written. */
function withAudio(): SidecarContext {
  const root = mkdtempSync(join(tmpdir(), "python-"))
  const runtime = join(root, "resources", "audiocpp")
  const audio = join(root, "audio")
  mkdirSync(runtime, { recursive: true })
  mkdirSync(audio, { recursive: true })
  writeFileSync(join(runtime, exe("audiocpp_server")), "")
  writeFileSync(join(audio, SERVER_CONFIG), '{"models":[]}')
  return {
    packaged: true,
    backendDir: root,
    binariesDir: join(root, "resources"),
    host: "127.0.0.1",
    apiPort: 1,
    dataDir: root,
    secret: "s",
    audioPort: 9998,
    audioUrl: "http://127.0.0.1:9998",
    audioModelsDir: audio,
    audioBinariesDir: runtime,
  }
}

test("the API is told where the staged eSpeak is, as the server is", () => {
  // audio.cpp's Kitten reads eSpeak's paths only from the config the API
  // writes, not from the server's environment as Kokoro does.
  const ctx = withAudio()
  const api = apiSpec(ctx).env
  const server = audiocppSpec(ctx)?.env ?? {}

  assert.equal(
    api.SURFSENSE_LOCAL_AUDIO_ESPEAK_DATA,
    join(ctx.audioBinariesDir ?? "", "espeak", "espeak-ng-data")
  )
  assert.ok(api.SURFSENSE_LOCAL_AUDIO_ESPEAK_LIBRARY)
  assert.equal(api.SURFSENSE_LOCAL_AUDIO_ESPEAK_LIBRARY, server.AUDIOCPP_ESPEAK_LIBRARY)
})

test("the API is told the shell's pid, the root of what counts as the app", () => {
  // The usage panel walks every process under this one: each sidecar, the
  // router's model workers, and Chromium's own helpers.
  const api = apiSpec(withAudio()).env

  assert.equal(api.SURFSENSE_LOCAL_SHELL_PID, String(process.pid))
})

test("under pnpm dev a worker is the app's own child, so it dies with the app", () => {
  // Under `uv run` it ran a level lower, which Windows does not kill with the
  // app: after a Ctrl-C the last session's Studio worker took the next jobs.
  const ctx = { ...withAudio(), packaged: false }
  const venvPython = isWindows
    ? join(".venv", "Scripts", "python.exe")
    : join(".venv", "bin", "python")

  const worker = workerSpec(ctx, "studio")

  assert.equal(worker.cmd, join(ctx.backendDir, venvPython))
  assert.deepEqual(worker.args, ["worker.py", "studio"])
})

/** The context boot builds on a host where opencode is staged. */
function withAgent(): SidecarContext {
  return {
    ...withAudio(),
    opencodePort: 4321,
    opencodePassword: "launch-password",
    opencodeUrl: "http://127.0.0.1:4321",
    docxSnapshotKey: "snapshot-key",
  }
}

test("the API is told where the agent will be and its password", () => {
  // Chosen at boot, before opencode exists: the API writes its config later.
  const api = apiSpec(withAgent()).env

  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_URL, "http://127.0.0.1:4321")
  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_PASSWORD, "launch-password")
})

test("a worker is never told the agent's password", () => {
  // Plugin runs start from a worker's environment; the password opens the agent's API.
  for (const queue of ["ingest", "studio"] as const) {
    const worker = workerSpec(withAgent(), queue).env

    assert.equal(worker.SURFSENSE_LOCAL_OPENCODE_PASSWORD, undefined, queue)
    assert.equal(worker.SURFSENSE_LOCAL_OPENCODE_URL, undefined, queue)
  }
})

test("the API is told the key Electron presents when it prints Word previews", () => {
  // Loopback is open to every local process; only the holder of this key may
  // take a snapshot request or post the pages the agent checks.
  const api = apiSpec(withAgent()).env

  assert.equal(api.SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY, "snapshot-key")
})

test("a worker is never told the snapshot key", () => {
  for (const queue of ["ingest", "studio"] as const) {
    const worker = workerSpec(withAgent(), queue).env

    assert.equal(worker.SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY, undefined, queue)
  }
})

test("without a staged opencode the API is told of no agent", () => {
  const api = apiSpec(withAudio()).env

  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_URL, undefined)
  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_PASSWORD, undefined)
})
