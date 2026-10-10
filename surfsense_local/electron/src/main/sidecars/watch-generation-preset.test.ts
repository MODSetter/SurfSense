import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { LLAMACPP_SIDECAR, PRESET_FILE } from "./llamacpp.ts"
import { exe } from "./platform.ts"
import type { SidecarControl, Sidecars } from "./supervisor.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"
import { watchGenerationPreset } from "./watch-generation-preset.ts"

/** A staged llama.cpp build and a models folder, the preset not yet written. */
function staged(): { ctx: SidecarContext; preset: string } {
  const root = mkdtempSync(join(tmpdir(), "watch-preset-"))
  const binaries = join(root, "llamacpp")
  const models = join(root, "models")
  mkdirSync(binaries, { recursive: true })
  mkdirSync(models, { recursive: true })
  writeFileSync(join(binaries, exe("llama-server")), "")
  return {
    ctx: {
      packaged: true,
      backendDir: root,
      binariesDir: root,
      host: "127.0.0.1",
      apiPort: 1,
      dataDir: root,
      secret: "s",
      llamacppPort: 9997,
      llamacppModelsDir: models,
      llamacppBinariesDir: binaries,
    },
    preset: join(models, PRESET_FILE),
  }
}

/** A control that records what a watcher does, instead of spawning anything. */
function recording(): {
  control: SidecarControl
  started: SidecarSpec[]
  stopped: string[]
  running: Sidecars
} {
  const running: Sidecars = new Map()
  const started: SidecarSpec[] = []
  const stopped: string[] = []
  return {
    running,
    started,
    stopped,
    control: {
      running,
      start: (spec) => {
        started.push(spec)
        running.set(spec.name, {} as never)
      },
      stop: async (name) => {
        stopped.push(name)
        running.delete(name)
      },
    },
  }
}

/** Resolves once `condition` holds, or fails after `ms`. */
async function until(condition: () => boolean, ms = 3000): Promise<void> {
  const deadline = Date.now() + ms
  while (!condition()) {
    if (Date.now() > deadline) throw new Error("condition never held")
    await new Promise((resolve) => setTimeout(resolve, 5))
  }
}

const settle = (ms = 40): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms))

test("restarts llama-server when the API rewrites the preset", async () => {
  const { ctx, preset } = staged()
  const rec = recording()
  // llama-server starts with the others at boot, so a rewrite restarts it.
  rec.running.set(LLAMACPP_SIDECAR, {} as never)
  const stop = watchGenerationPreset({
    ctx,
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    writeFileSync(preset, "[model]\n")
    await until(() => rec.started.length === 1)
    assert.equal(rec.started[0].name, LLAMACPP_SIDECAR)
    assert.deepEqual(rec.stopped, [LLAMACPP_SIDECAR])
  } finally {
    stop()
  }
})

test("leaves a running llama-server alone while the preset is unchanged", async () => {
  const { ctx } = staged()
  const rec = recording()
  rec.running.set(LLAMACPP_SIDECAR, {} as never)
  const stop = watchGenerationPreset({
    ctx,
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    await settle()
    assert.deepEqual(rec.started, [])
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
  }
})

test("stops reconciling once the app is shutting down", async () => {
  const { ctx, preset } = staged()
  const rec = recording()
  let stopping = false
  const stop = watchGenerationPreset({
    ctx,
    control: rec.control,
    stopping: () => stopping,
    pollMs: 5,
  })
  try {
    stopping = true
    writeFileSync(preset, "[model]\n")
    await settle()
    assert.deepEqual(rec.started, [])
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
  }
})

test("watches nothing without a models folder", () => {
  const { ctx } = staged()
  const rec = recording()
  const stop = watchGenerationPreset({
    ctx: { ...ctx, llamacppModelsDir: undefined },
    control: rec.control,
    stopping: () => false,
  })

  assert.equal(typeof stop, "function")
  stop()
})