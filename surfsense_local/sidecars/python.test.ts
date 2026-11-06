import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { audiocppSpec, SERVER_CONFIG } from "./audiocpp.ts"
import { exe, isWindows } from "./platform.ts"
import {
  apiSpec,
  BACKEND_BINARY,
  FRESH_START_EXIT_CODE,
  WORKER_QUEUES,
  workerSpec,
} from "./python.ts"
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

test("a worker that exits to free its memory is started again; the API never is", () => {
  const ctx = withAudio()
  for (const queue of WORKER_QUEUES) {
    assert.equal(workerSpec(ctx, queue).freshStartExitCode, FRESH_START_EXIT_CODE)
  }
  // backend/worker/fresh_start.py exits with the same number.
  assert.equal(FRESH_START_EXIT_CODE, 75)
  assert.equal(apiSpec(ctx).freshStartExitCode, undefined)
})

test("every Python sidecar runs numpy's OpenBLAS on one thread unless the user chose a count", () => {
  const ctx = withAudio()
  const specs = () => [apiSpec(ctx), ...WORKER_QUEUES.map((queue) => workerSpec(ctx, queue))]
  const before = process.env.OPENBLAS_NUM_THREADS
  try {
    delete process.env.OPENBLAS_NUM_THREADS
    for (const spec of specs()) assert.equal(spec.env.OPENBLAS_NUM_THREADS, "1")
    process.env.OPENBLAS_NUM_THREADS = "4"
    for (const spec of specs()) assert.equal(spec.env.OPENBLAS_NUM_THREADS, "4")
  } finally {
    if (before === undefined) delete process.env.OPENBLAS_NUM_THREADS
    else process.env.OPENBLAS_NUM_THREADS = before
  }
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

test("packaged, the API and every worker run the one frozen backend with their role", () => {
  // One binary carries both roles; the first argument picks one, and a
  // missing or unknown role exits instead of starting a server.
  const ctx = withAudio()
  const binary = join(ctx.binariesDir, "backend", exe(BACKEND_BINARY))

  const api = apiSpec(ctx)

  assert.equal(api.cmd, binary)
  assert.deepEqual(api.args, ["api"])
  for (const queue of WORKER_QUEUES) {
    const worker = workerSpec(ctx, queue)

    assert.equal(worker.cmd, binary, queue)
    assert.deepEqual(worker.args, ["worker", queue])
  }
})

test("every backend queue has its worker, links from the web included", () => {
  // A queue nothing drains holds its jobs forever: links added from the web
  // stayed pending until the plugins queue got its worker.
  assert.deepEqual([...WORKER_QUEUES], ["ingest", "studio", "plugins"])

  const plugins = workerSpec(withAudio(), "plugins")

  assert.equal(plugins.name, "worker-plugins")
  assert.deepEqual(plugins.args.slice(-1), ["plugins"])
})

/** The context boot builds on a host where opencode is staged. */
function withAgent(): SidecarContext {
  return {
    ...withAudio(),
    opencodePort: 4321,
    opencodePassword: "launch-password", // pragma: allowlist secret
    opencodeUrl: "http://127.0.0.1:4321",
    opencodeProxyPort: 5555,
    docxSnapshotKey: "snapshot-key",
  }
}

test("the API is told where the agent will be and its password", () => {
  // Chosen at boot, before opencode exists: the API writes its config later.
  const api = apiSpec(withAgent()).env

  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_URL, "http://127.0.0.1:4321")
  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_PASSWORD, "launch-password")
})

test("the API is told where to run the proxy opencode's connections go through", () => {
  const api = apiSpec(withAgent()).env

  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_PROXY_PORT, "5555")
})

test("a worker is never told the agent's password", () => {
  // Plugin runs start from a worker's environment; the password opens the agent's API.
  for (const queue of WORKER_QUEUES) {
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
  for (const queue of WORKER_QUEUES) {
    const worker = workerSpec(withAgent(), queue).env

    assert.equal(worker.SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY, undefined, queue)
  }
})

test("without a staged opencode the API is told of no agent", () => {
  const api = apiSpec(withAudio()).env

  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_URL, undefined)
  assert.equal(api.SURFSENSE_LOCAL_OPENCODE_PASSWORD, undefined)
})

/** The context boot builds on a host where audio.cpp is staged. */
function withTranscription(): SidecarContext {
  return {
    ...withAudio(),
    transcriptionPort: 9997,
    transcriptionUrl: "http://127.0.0.1:9997",
  }
}

test("the API is told where the speech recognition server is", () => {
  const api = apiSpec(withTranscription()).env

  assert.equal(api.SURFSENSE_LOCAL_TRANSCRIPTION_BASE_URL, "http://127.0.0.1:9997")
})

test("a worker is never told where the speech recognition server is", () => {
  // Every request goes through the API's gate, which puts dictation first.
  for (const queue of WORKER_QUEUES) {
    const worker = workerSpec(withTranscription(), queue).env

    assert.equal(worker.SURFSENSE_LOCAL_TRANSCRIPTION_BASE_URL, undefined, queue)
  }
})

test("without a staged audio.cpp the API is told of no speech recognition server", () => {
  const ctx = withTranscription()
  const api = apiSpec({ ...ctx, audioBinariesDir: join(ctx.binariesDir, "absent") }).env

  assert.equal(api.SURFSENSE_LOCAL_TRANSCRIPTION_BASE_URL, undefined)
})

test("the API and every worker hear where a moved models folder and the shell's settings are", () => {
  const ctx: SidecarContext = {
    ...withAudio(),
    embeddingModelsDir: join("D:", "SurfSense-Models", "embeddings"),
    shellSettingsDir: join("C:", ".surfsense", "electron"),
  }

  for (const env of [apiSpec(ctx).env, workerSpec(ctx, "ingest").env]) {
    assert.equal(env.SURFSENSE_LOCAL_EMBEDDING_MODELS_DIR, ctx.embeddingModelsDir)
    assert.equal(env.SURFSENSE_LOCAL_SHELL_SETTINGS_DIR, ctx.shellSettingsDir)
    assert.equal(env.SURFSENSE_LOCAL_MODEL_STORAGE_UNAVAILABLE, undefined)
  }
})

test("workers hear that the models drive is missing, so downloads wait for it", () => {
  const env = apiSpec({ ...withAudio(), modelStorageUnavailable: true }).env
  assert.equal(env.SURFSENSE_LOCAL_MODEL_STORAGE_UNAVAILABLE, "1")
})

test("an install that never moved anything sets none of the storage variables", () => {
  const env = apiSpec(withAudio()).env
  assert.equal(env.SURFSENSE_LOCAL_EMBEDDING_MODELS_DIR, undefined)
  assert.equal(env.SURFSENSE_LOCAL_SHELL_SETTINGS_DIR, undefined)
})
