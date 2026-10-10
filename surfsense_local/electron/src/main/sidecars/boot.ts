/**
 * Bring up the API and the model runtimes: pick ports, build the specs, start
 * them, and follow the files the API rewrites.
 *
 * Everything a host must answer — the paths, the packaged flag and the secret —
 * arrives in `BootContext`, so Electron and the container run this same code.
 * Electron keeps only what is its own: the window, the keychain and the crash
 * notice it sends the renderer.
 */
import { randomBytes } from "node:crypto"
import { existsSync, mkdirSync, rmSync } from "node:fs"
import { join } from "node:path"

import { getFreePort, waitForHealth } from "../net.ts"
import { audiocppSpec } from "./audiocpp.ts"
import { llamacppSpec } from "./llamacpp.ts"
import {
  binaryPath as opencodeBinaryPath,
  configPath as opencodeConfigPath,
  opencodeSpec,
  OPENCODE_SIDECAR,
} from "./opencode.ts"
import { prepareOpencodeHome } from "./opencode-home.ts"
import { recordOpencode, stopLeftoverOpencode } from "./opencode-leftovers.ts"
import { apiSpec, workerSpec } from "./python.ts"
import { binaryPath as sdcppBinaryPath } from "./sdcpp.ts"
import {
  sidecarControl,
  startAll,
  type Sidecars,
  type SidecarControl,
} from "./supervisor.ts"
import type { CrashHandler, SidecarContext, SidecarSpec } from "./types.ts"
import { watchAudioModels } from "./watch-audio-models.ts"
import { watchGenerationPreset } from "./watch-generation-preset.ts"
import { watchImageModel } from "./watch-image-model.ts"

/** What only the host knows: its paths, the packaged flag and the secret. */
export interface BootContext {
  packaged: boolean
  /** Dev cwd for `uv run`; packaged: the frozen backend beside the app. */
  backendDir: string
  /** resources/ root in the packaged app; where the binaries are unpacked. */
  binariesDir: string
  /** The install's data folder: models, images, audio, the agent. */
  dataDir: string
  /** Per-install secret the backend encrypts provider API keys with. */
  secret: string
  /** Packaged: read-only bundled embedding, voice and parser packs. */
  modelsDir: string
  /** The staged llama.cpp build; absent from disk means no local generation. */
  llamacppBinariesDir: string
  /** The staged audio.cpp build; absent from disk means no voices. */
  audioBinariesDir: string
  /** The staged sd-server build; absent means the API offers no image models. */
  sdcppBinariesDir: string
  /** The staged opencode; absent means no agent. */
  opencodeBinariesDir: string
}

export interface Booted {
  apiUrl: string
  dataDir: string
  /** The assembled context, for the Electron-only parts that read from it. */
  ctx: SidecarContext
  sidecars: Sidecars
  /** Stop the watchers. The caller stops the sidecars themselves. */
  stopWatching: () => void
  /** Resolves once the API answers /health; rejects if it dies first. */
  waitHealthy: () => Promise<void>
}

export async function bootSidecars(
  context: BootContext,
  onCrash: CrashHandler,
): Promise<Booted> {
  const host = "127.0.0.1"
  const { packaged, dataDir } = context
  const apiPort = await getFreePort(host)

  const ctx: SidecarContext = {
    packaged,
    backendDir: context.backendDir,
    binariesDir: context.binariesDir,
    host,
    apiPort,
    dataDir,
    secret: context.secret,
    modelsDir: context.modelsDir,
    // Unconditional, because dev needs runtimes too and dataDir already keeps
    // dev models out of the real install.
    llamacppBinariesDir: context.llamacppBinariesDir,
    audioBinariesDir: context.audioBinariesDir,
  }
  ctx.llamacppPort = await getFreePort(host)
  ctx.llamacppModelsDir = join(dataDir, "models")
  ctx.llamacppUrl = `http://${host}:${ctx.llamacppPort}`
  // llama-server exits 1 when --models-dir does not exist, and on a clean
  // install nothing has created it yet: only a download would, and a download
  // needs the runtime. Measured: "failed to initialize router models: error:
  // '<path>' does not exist or is not a directory".
  mkdirSync(ctx.llamacppModelsDir, { recursive: true })

  // Dev too, as for llama.cpp: podcasts are voiced by the binary that ships.
  ctx.audioPort = await getFreePort(host)
  ctx.audioUrl = `http://${host}:${ctx.audioPort}`
  ctx.audioModelsDir = join(dataDir, "audio")
  mkdirSync(ctx.audioModelsDir, { recursive: true })

  // Only a host with a staged sd-server gets an images dir: without it the API
  // offers no image models, rather than downloads that can never run.
  const sdcppBinariesDir = context.sdcppBinariesDir
  if (existsSync(sdcppBinaryPath({ ...ctx, sdcppBinariesDir }))) {
    ctx.sdcppBinariesDir = sdcppBinariesDir
    ctx.imagePort = await getFreePort(host)
    ctx.imageModelsDir = join(dataDir, "images")
    ctx.imageUrl = `http://${host}:${ctx.imagePort}`
  }

  // Only a host with a staged opencode gets an agent: the port and password are
  // chosen now so the API knows where it will be, and opencode itself waits for
  // the API's configuration (watchAgentConfig).
  const opencodeBinariesDir = context.opencodeBinariesDir
  if (existsSync(opencodeBinaryPath({ ...ctx, opencodeBinariesDir }))) {
    ctx.opencodeBinariesDir = opencodeBinariesDir
    ctx.opencodePort = await getFreePort(host)
    ctx.opencodePassword = randomBytes(32).toString("base64url")
    ctx.docxSnapshotKey = randomBytes(32).toString("base64url")
    ctx.opencodeUrl = `http://${host}:${ctx.opencodePort}`
    ctx.agentDir = join(dataDir, "agent")
    mkdirSync(ctx.agentDir, { recursive: true })
    await stopLeftoverOpencode(ctx.agentDir, host)
    // Each run's API writes its own; the last run's names a key this one never made.
    rmSync(opencodeConfigPath(ctx.agentDir), { force: true })
  }

  // llamacppSpec is null in dev, where no binary is staged. sd-server is absent
  // here on purpose: watchImageModel owns it, because only the API knows which
  // model was chosen.
  const specs = [
    apiSpec(ctx),
    workerSpec(ctx, "ingest"),
    workerSpec(ctx, "studio"),
    llamacppSpec(ctx),
    // Null until the API's config names an audio model.
    audiocppSpec(ctx),
  ].filter((s): s is SidecarSpec => s !== null)
  const sidecars = startAll(specs, onCrash)
  const control = sidecarControl(sidecars, onCrash)

  let stopping = false
  const stopWatchers = [
    watchImageModel({ ctx, control, stopping: () => stopping }),
    watchGenerationPreset({ ctx, control, stopping: () => stopping }),
    watchAudioModels({ ctx, control, stopping: () => stopping }),
    watchAgentConfig({ ctx, control, stopping: () => stopping }),
  ]

  return {
    apiUrl: `http://${host}:${apiPort}`,
    dataDir,
    ctx,
    sidecars,
    stopWatching: () => {
      stopping = true
      for (const stop of stopWatchers) stop()
    },
    // gate on the API only; fail fast if it dies during startup. llama-server is
    // best-effort (its state shows via /llm/providers; an early exit hits onCrash).
    // The caller waits, so it holds the sidecars before anything can fail.
    waitHealthy: () => waitForHealth(host, apiPort, { child: sidecars.get("api") }),
  }
}

// opencode starts the first time a thread needs the agent, which the API says
// by writing its configuration. A rewrite is not a restart: opencode reads the
// file per folder, and the API makes it read it again (`POST /global/dispose`),
// so no turn is cut off by a restart it did not ask for. Removing the file stops
// opencode; a crash restarts it, at most once per AGENT_RESTART_MS.
const AGENT_RESTART_MS = 10_000

function watchAgentConfig(options: {
  ctx: SidecarContext
  control: SidecarControl
  stopping: () => boolean
}): () => void {
  const { ctx, control, stopping } = options
  if (ctx.agentDir == null || ctx.opencodeBinariesDir == null) return () => {}
  const agentDir = ctx.agentDir
  const config = opencodeConfigPath(agentDir)
  let lastStart = 0

  const reconcile = async () => {
    if (stopping()) return
    const child = control.running.get(OPENCODE_SIDECAR)
    const running = child != null && child.exitCode === null && child.signalCode === null
    const wanted = existsSync(config)
    if (wanted === running) return

    if (!wanted) {
      await control.stop(OPENCODE_SIDECAR)
      return
    }
    if (Date.now() - lastStart < AGENT_RESTART_MS) return
    const spec = opencodeSpec(ctx)
    if (!spec) return
    prepareOpencodeHome(agentDir)
    control.start(spec)
    lastStart = Date.now()
    const pid = control.running.get(OPENCODE_SIDECAR)?.pid
    if (pid != null && ctx.opencodePort != null && ctx.opencodePassword != null) {
      recordOpencode(agentDir, {
        pid,
        port: ctx.opencodePort,
        password: ctx.opencodePassword,
      })
    }
  }

  const timer = setInterval(() => {
    void reconcile().catch(() => {
      // Mid-write or mid-restart; the next tick tries again.
    })
    // Faster than the other watchers: someone is waiting on their first agent turn.
  }, 2000)
  timer.unref()
  return () => clearInterval(timer)
}