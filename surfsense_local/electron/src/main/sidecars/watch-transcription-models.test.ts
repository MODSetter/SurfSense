import assert from "node:assert/strict"
import type { ChildProcess } from "node:child_process"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { SERVER_CONFIG } from "./audiocpp.ts"
import {
  AUDIOCPP_TRANSCRIPTION_SIDECAR,
  TRANSCRIPTION_CONFIG,
} from "./audiocpp-transcription.ts"
import { exe } from "./platform.ts"
import type { SidecarControl, Sidecars } from "./supervisor.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"
import { watchTranscriptionModels } from "./watch-transcription-models.ts"

/** A staged audio.cpp build and an audio folder, no speech model named yet. */
function staged(): { ctx: SidecarContext; config: string; voices: string } {
  const root = mkdtempSync(join(tmpdir(), "watch-transcription-"))
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
      transcriptionPort: 9997,
      audioModelsDir: audio,
      audioBinariesDir: binaries,
    },
    config: join(audio, TRANSCRIPTION_CONFIG),
    voices: join(audio, SERVER_CONFIG),
  }
}

/** A child as the supervisor keeps it: alive until it exits. */
type FakeChild = { exitCode: number | null; signalCode: NodeJS.Signals | null }

/** A control that records what a watcher does, instead of spawning anything. */
function recording(): {
  control: SidecarControl
  started: SidecarSpec[]
  stopped: string[]
  running: Sidecars
  /** The last child started, exited as a crash leaves it: still in `running`. */
  crash: () => void
} {
  const running: Sidecars = new Map()
  const started: SidecarSpec[] = []
  const stopped: string[] = []
  let last: FakeChild | undefined
  return {
    running,
    started,
    stopped,
    crash: () => {
      if (last) last.exitCode = 1
    },
    control: {
      running,
      start: (spec) => {
        started.push(spec)
        last = { exitCode: null, signalCode: null }
        running.set(spec.name, last as unknown as ChildProcess)
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

/** Wait long enough for a few short-interval polls to have run. */
const settle = (ms = 60): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms))

/** A watcher on a fast poll and a clock the test moves. */
function watching() {
  const setup = staged()
  const rec = recording()
  const clock = { now: 0 }
  const stop = watchTranscriptionModels({
    ctx: setup.ctx,
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
    now: () => clock.now,
  })
  return { ...setup, rec, clock, stop }
}

test("starts the speech recognition server once the API names a speech model", async () => {
  const { config, rec, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    assert.equal(rec.started[0].name, AUDIOCPP_TRANSCRIPTION_SIDECAR)
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
  }
})

test("restarts it when the API rewrites its config", async () => {
  const { config, rec, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    writeFileSync(config, '{"models":[1,2]}')
    await until(() => rec.started.length === 2)
    assert.deepEqual(rec.stopped, [AUDIOCPP_TRANSCRIPTION_SIDECAR])
  } finally {
    stop()
  }
})

test("stops it when the last speech model is gone", async () => {
  const { config, rec, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    rmSync(config)
    await until(() => rec.stopped.length === 1)
    await settle()
    assert.equal(rec.started.length, 1)
    assert.equal(rec.running.has(AUDIOCPP_TRANSCRIPTION_SIDECAR), false)
  } finally {
    stop()
  }
})

test("starts nothing while no speech model is named", async () => {
  const { rec, stop } = watching()
  try {
    await settle()
    assert.deepEqual(rec.started, [])
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
  }
})

test("a voice install leaves it running", async () => {
  // The API rewrites server.json on every voice install and at each start.
  const { config, voices, rec, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    writeFileSync(voices, '{"models":[1]}')
    await settle()
    assert.equal(rec.started.length, 1)
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
  }
})

test("restarts it after a crash, at most once every 10 s", async () => {
  const { config, rec, clock, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    clock.now = 4_000
    rec.crash()
    await settle()
    assert.equal(rec.started.length, 1)

    clock.now = 10_000
    await until(() => rec.started.length === 2)
    assert.equal(rec.started[1].name, AUDIOCPP_TRANSCRIPTION_SIDECAR)
  } finally {
    stop()
  }
})

test("gives up after 3 crashes in 5 minutes", async () => {
  const { config, rec, clock, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    for (const at of [20_000, 40_000]) {
      clock.now = at
      rec.crash()
      await until(() => rec.started.length === (at === 20_000 ? 2 : 3))
    }
    clock.now = 60_000
    rec.crash()
    await settle()
    // Not even once the crashes are long past.
    clock.now = 10 * 60_000
    await settle()
    assert.equal(rec.started.length, 3)
  } finally {
    stop()
  }
})

test("keeps restarting crashes spread wider than 5 minutes", async () => {
  const { config, rec, clock, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    for (const [at, starts] of [
      [3 * 60_000, 2],
      [6 * 60_000, 3],
      [9 * 60_000, 4],
    ]) {
      clock.now = at
      rec.crash()
      await until(() => rec.started.length === starts)
    }
  } finally {
    stop()
  }
})

test("a new speech model brings it back after it gave up", async () => {
  const { config, rec, clock, stop } = watching()
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    for (const [at, starts] of [
      [20_000, 2],
      [40_000, 3],
    ]) {
      clock.now = at
      rec.crash()
      await until(() => rec.started.length === starts)
    }
    clock.now = 60_000
    rec.crash()
    await settle()
    assert.equal(rec.started.length, 3)

    writeFileSync(config, '{"models":[2]}')
    await until(() => rec.started.length === 4)
  } finally {
    stop()
  }
})

test("restarts nothing while the app is quitting", async () => {
  const { ctx, config } = staged()
  const rec = recording()
  const clock = { now: 0 }
  let quitting = false
  const stop = watchTranscriptionModels({
    ctx,
    control: rec.control,
    stopping: () => quitting,
    pollMs: 5,
    now: () => clock.now,
  })
  try {
    writeFileSync(config, '{"models":[1]}')
    await until(() => rec.started.length === 1)
    quitting = true
    rec.crash()
    clock.now = 60_000
    writeFileSync(config, '{"models":[1,2]}')
    await settle()
    assert.equal(rec.started.length, 1)
  } finally {
    stop()
  }
})

test("watches nothing without an audio folder", () => {
  const { ctx } = staged()
  const rec = recording()
  const stop = watchTranscriptionModels({
    ctx: { ...ctx, audioModelsDir: undefined },
    control: rec.control,
    stopping: () => false,
  })

  assert.equal(typeof stop, "function")
  stop()
})
