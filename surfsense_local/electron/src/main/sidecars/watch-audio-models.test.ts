import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { AUDIOCPP_SIDECAR, SERVER_CONFIG } from "./audiocpp.ts"
import { exe } from "./platform.ts"
import type { SidecarControl, Sidecars } from "./supervisor.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"
import { watchAudioModels } from "./watch-audio-models.ts"

/** A staged audio.cpp build and an audio folder, the config not yet written. */
function staged(): { ctx: SidecarContext; config: string } {
  const root = mkdtempSync(join(tmpdir(), "watch-audio-"))
  const binaries = join(root, "audiocpp")
  const audio = join(root, "audio")
  mkdirSync(binaries, { recursive: true })
  mkdirSync(audio, { recursive: true })
  writeFileSync(join(binaries, exe("audiocpp_server")), "")
  return {
    ctx: {
      packaged: true,
      backendDir: root,
      binariesDir: root,
      host: "127.0.0.1",
      apiPort: 1,
      dataDir: root,
      secret: "s",
      audioPort: 9998,
      audioModelsDir: audio,
      audioBinariesDir: binaries,
    },
    config: join(audio, SERVER_CONFIG),
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

test("starts audiocpp once the API names a model", async () => {
  const { ctx, config } = staged()
  const rec = recording()
  const stop = watchAudioModels({
    ctx,
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    writeFileSync(config, '{"models":[]}')
    await until(() => rec.started.length === 1)
    assert.equal(rec.started[0].name, AUDIOCPP_SIDECAR)
    // Nothing was running before the config appeared.
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
  }
})

test("restarts audiocpp when the API rewrites its config", async () => {
  const { ctx, config } = staged()
  const rec = recording()
  const stop = watchAudioModels({
    ctx,
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    writeFileSync(config, '{"models":[1,2]}')
    await until(() => rec.started.length === 2)
    assert.deepEqual(rec.stopped, [AUDIOCPP_SIDECAR])
  } finally {
    stop()
  }
})

test("starts nothing while no model is named", async () => {
  const { ctx } = staged()
  const rec = recording()
  const stop = watchAudioModels({
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

test("watches nothing without an audio folder", () => {
  const { ctx } = staged()
  const rec = recording()
  const stop = watchAudioModels({
    ctx: { ...ctx, audioModelsDir: undefined },
    control: rec.control,
    stopping: () => false,
  })

  assert.equal(typeof stop, "function")
  stop()
})