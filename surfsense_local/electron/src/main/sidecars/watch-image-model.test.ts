import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs"
import http from "node:http"
import type { AddressInfo } from "node:net"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { exe } from "./platform.ts"
import { SDCPP_SIDECAR } from "./sdcpp.ts"
import type { SidecarControl, Sidecars } from "./supervisor.ts"
import type { SidecarContext, SidecarSpec } from "./types.ts"
import { watchImageModel } from "./watch-image-model.ts"

const ROUTE = "/llm/image/local/runtime"

/** A staged sd-server, an image folder with one build of a model, and a chosen runtime. */
function staged(): { ctx: SidecarContext; images: string; binaries: string } {
  const root = mkdtempSync(join(tmpdir(), "watch-image-"))
  const binaries = join(root, "sdcpp")
  const images = join(root, "images")
  mkdirSync(binaries, { recursive: true })
  mkdirSync(images, { recursive: true })
  writeFileSync(join(binaries, exe("sd-server")), "")
  writeFileSync(join(images, "sdxl.gguf"), "")
  return {
    ctx: {
      packaged: true,
      backendDir: root,
      binariesDir: root,
      host: "127.0.0.1",
      apiPort: 1,
      dataDir: root,
      secret: "s",
      imagePort: 9998,
      imageModelsDir: images,
      imageUrl: "http://127.0.0.1:9998",
      sdcppBinariesDir: binaries,
    },
    images,
    binaries,
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

/** The API's runtime route, answering whatever the chosen model is now. */
async function fakeApi(runtime: () => unknown) {
  const server = http.createServer((_request, response) => {
    if (_request.url !== ROUTE) {
      response.writeHead(404).end()
      return
    }
    response.writeHead(200, { "content-type": "application/json" })
    response.end(JSON.stringify(runtime()))
  })
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve))
  const port = (server.address() as AddressInfo).port
  return {
    port,
    close: () =>
      new Promise<void>((resolve) => {
        server.closeAllConnections()
        server.close(() => resolve())
      }),
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

test("starts sd-server for the model the API chose", async () => {
  const { ctx } = staged()
  const api = await fakeApi(() => ({
    files: [{ flag: "-m", path: "sdxl.gguf" }],
    args: ["--steps", "20"],
  }))
  const rec = recording()
  const stop = watchImageModel({
    ctx: { ...ctx, apiPort: api.port },
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    await until(() => rec.started.length === 1)
    assert.equal(rec.started[0].name, SDCPP_SIDECAR)
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
    await api.close()
  }
})

test("restarts sd-server when the API changes the model's flags", async () => {
  const { ctx } = staged()
  let args = ["--steps", "20"]
  const api = await fakeApi(() => ({
    files: [{ flag: "-m", path: "sdxl.gguf" }],
    args,
  }))
  const rec = recording()
  const stop = watchImageModel({
    ctx: { ...ctx, apiPort: api.port },
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    await until(() => rec.started.length === 1)
    args = ["--steps", "30"]
    await until(() => rec.started.length === 2)
    assert.deepEqual(rec.stopped, [SDCPP_SIDECAR])
  } finally {
    stop()
    await api.close()
  }
})

test("stops sd-server when the API names no model", async () => {
  const { ctx } = staged()
  let files: { flag: string; path: string }[] = [{ flag: "-m", path: "sdxl.gguf" }]
  const api = await fakeApi(() => ({ files, args: [] }))
  const rec = recording()
  const stop = watchImageModel({
    ctx: { ...ctx, apiPort: api.port },
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    await until(() => rec.started.length === 1)
    files = []
    await until(() => rec.stopped.length === 1)
    assert.deepEqual(rec.stopped, [SDCPP_SIDECAR])
    assert.equal(rec.started.length, 1)
  } finally {
    stop()
    await api.close()
  }
})

test("an API that is down leaves the sidecar as it is", async () => {
  const { ctx } = staged()
  // Nothing listens here: the fetch rejects, and the watcher must not crash.
  const rec = recording()
  const stop = watchImageModel({
    ctx: { ...ctx, apiPort: 1 },
    control: rec.control,
    stopping: () => false,
    pollMs: 5,
  })
  try {
    await new Promise((resolve) => setTimeout(resolve, 40))
    assert.deepEqual(rec.started, [])
    assert.deepEqual(rec.stopped, [])
  } finally {
    stop()
  }
})

test("watches nothing without an image folder", () => {
  const { ctx } = staged()
  const rec = recording()
  const stop = watchImageModel({
    ctx: { ...ctx, imageModelsDir: undefined },
    control: rec.control,
    stopping: () => false,
  })

  assert.equal(typeof stop, "function")
  stop()
})