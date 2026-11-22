import assert from "node:assert/strict"
import {
  existsSync,
  linkSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
} from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"
import test from "node:test"

import { removeInterruptedCopy, removeOldCopies } from "./clean-up-old-copies.ts"
import { LOCATION_FILE, readStorageLocation, writeStorageLocation } from "./location-file.ts"
import { hasMarker, writeMarker } from "./marker.ts"
import { planMove, type MovePlan } from "./plan-move.ts"
import { resolveStorage } from "./resolve-storage.ts"
import { MoveFailedError, runMove, type MoveProgress } from "./run-move.ts"

const temp = () => mkdtempSync(join(tmpdir(), "surfsense-move-"))
const APP = "/opt/not-here/SurfSense"

function databaseValue(path: string): unknown {
  const db = new DatabaseSync(path)
  const row = db.prepare("SELECT v FROM t").get() as { v: unknown }
  db.close()
  return row.v
}

function install(): string {
  const base = temp()
  mkdirSync(join(base, "electron"))
  writeFileSync(join(base, "electron", "secret.bin"), "keychain")
  const db = new DatabaseSync(join(base, "surfsense.db"))
  db.exec("CREATE TABLE t (v TEXT)")
  db.prepare("INSERT INTO t VALUES (?)").run("database")
  db.close()
  writeFileSync(join(base, "api-url"), "http://127.0.0.1:1")
  mkdirSync(join(base, "data", "t"), { recursive: true })
  writeFileSync(join(base, "data", "t", "a.txt"), "source text")
  mkdirSync(join(base, "models"))
  writeFileSync(join(base, "models", "m.gguf"), "weights")
  mkdirSync(join(base, "embeddings", "e"), { recursive: true })
  writeFileSync(join(base, "embeddings", "e", "model.onnx"), "embedder")
  return base
}

async function plan(base: string, kind: "data" | "models", picked: string | null): Promise<MovePlan> {
  const result = await planMove({
    kind,
    picked,
    storage: resolveStorage(base, readStorageLocation(base)),
    appFolder: APP,
  })
  assert.ok("plan" in result, `refused: ${JSON.stringify(result)}`)
  return result.plan
}

const move = (p: MovePlan, base: string, signal = new AbortController().signal, onProgress: (progress: MoveProgress) => void = () => {}) =>
  runMove({ plan: p, baseDir: base, signal, onProgress })

test("moving models carries the four model folders and nothing else", async () => {
  const base = install()
  const drive = temp()
  const p = await plan(base, "models", drive)

  await move(p, base)

  const root = join(drive, "SurfSense-Models")
  assert.equal(readFileSync(join(root, "models", "m.gguf"), "utf8"), "weights")
  assert.equal(readFileSync(join(root, "embeddings", "e", "model.onnx"), "utf8"), "embedder")
  assert.equal(existsSync(join(root, "surfsense.db")), false)
  assert.ok(hasMarker(root, "models"))
  assert.equal(readStorageLocation(base).modelsRoot, root)
})

test("the originals stay until a start has proved the new folder, then only the named ones go", async () => {
  const base = install()
  writeFileSync(join(base, "kept-by-the-user.txt"), "mine")
  await move(await plan(base, "models", temp()), base)

  assert.equal(readFileSync(join(base, "models", "m.gguf"), "utf8"), "weights")

  await removeOldCopies(base)

  assert.equal(existsSync(join(base, "models")), false)
  assert.equal(databaseValue(join(base, "surfsense.db")), "database")
  assert.equal(readFileSync(join(base, "kept-by-the-user.txt"), "utf8"), "mine")
  assert.equal(readStorageLocation(base).leftBehind, undefined)
})

test("moving all the data leaves Electron's folder, the secret and the location where they are", async () => {
  const base = install()
  const drive = temp()
  await move(await plan(base, "data", drive), base)
  await removeOldCopies(base)

  const root = join(drive, "SurfSense-Data")
  assert.equal(databaseValue(join(root, "surfsense.db")), "database")
  assert.equal(readFileSync(join(root, "models", "m.gguf"), "utf8"), "weights")
  assert.equal(existsSync(join(root, "electron")), false)
  assert.deepEqual(readdirSync(base).sort(), ["api-url", "electron", LOCATION_FILE].sort())
  assert.equal(readFileSync(join(base, "electron", "secret.bin"), "utf8"), "keychain")
  const storage = resolveStorage(base, readStorageLocation(base))
  assert.equal(storage.dataRoot, root)
  assert.equal(storage.modelsRoot, root)
})

test("moved models stay where they are when the data moves after them", async () => {
  const base = install()
  await move(await plan(base, "models", temp()), base)
  await removeOldCopies(base)
  const modelsRoot = readStorageLocation(base).modelsRoot

  await move(await plan(base, "data", temp()), base)
  await removeOldCopies(base)

  assert.equal(readStorageLocation(base).modelsRoot, modelsRoot)
  assert.equal(readFileSync(join(modelsRoot ?? "", "models", "m.gguf"), "utf8"), "weights")
})

test("a hard-linked file stays one file, or the data grows and the text cache forks", async () => {
  const base = install()
  writeFileSync(join(base, "data", "cached.txt"), "text")
  linkSync(join(base, "data", "cached.txt"), join(base, "data", "t", "linked.txt"))
  const drive = temp()

  await move(await plan(base, "data", drive), base)

  const root = join(drive, "SurfSense-Data", "data")
  assert.equal(statSync(join(root, "cached.txt")).nlink, 2)
  assert.equal(statSync(join(root, "cached.txt")).ino, statSync(join(root, "t", "linked.txt")).ino)
})

test("executable bits and modified times survive, or a staged binary stops running", { skip: process.platform === "win32" }, async () => {
  const base = install()
  const script = join(base, "data", "tool.sh")
  writeFileSync(script, "#!/bin/sh\n", { mode: 0o755 })
  const before = statSync(script)
  const drive = temp()

  await move(await plan(base, "data", drive), base)

  const after = statSync(join(drive, "SurfSense-Data", "data", "tool.sh"))
  assert.equal(after.mode & 0o777, 0o755)
  assert.equal(Math.round(after.mtimeMs / 1000), Math.round(before.mtimeMs / 1000))
})

test("a symbolic link into the moved folder follows it", { skip: process.platform === "win32" }, async () => {
  const base = install()
  symlinkSync(join(base, "data", "t", "a.txt"), join(base, "data", "absolute"))
  symlinkSync("t/a.txt", join(base, "data", "relative"))
  const drive = temp()

  await move(await plan(base, "data", drive), base)
  await removeOldCopies(base)

  const root = join(drive, "SurfSense-Data", "data")
  assert.equal(readFileSync(join(root, "absolute"), "utf8"), "source text")
  assert.equal(readFileSync(join(root, "relative"), "utf8"), "source text")
})

test("a real database in WAL mode arrives whole, with its uncheckpointed rows", async () => {
  const base = install()
  rmSync(join(base, "surfsense.db"))
  const db = new DatabaseSync(join(base, "surfsense.db"))
  db.exec("PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=0; CREATE TABLE t (v TEXT)")
  db.prepare("INSERT INTO t VALUES (?)").run("in the wal")
  // Left open, as a crashed run would: the rows live only in the -wal file.
  const drive = temp()

  await move(await plan(base, "data", drive), base)
  db.close()

  const moved = new DatabaseSync(join(drive, "SurfSense-Data", "surfsense.db"))
  assert.deepEqual({ ...moved.prepare("SELECT v FROM t").get() }, { v: "in the wal" })
  moved.close()
})

test("cancelling leaves the old location in charge and no partial copy", async () => {
  const base = install()
  const drive = temp()
  const p = await plan(base, "models", drive)
  const stop = new AbortController()
  stop.abort()

  await assert.rejects(move(p, base, stop.signal), (error: MoveFailedError) => error.reason === "canceled")

  assert.equal(readStorageLocation(base).modelsRoot, undefined)
  assert.equal(readStorageLocation(base).movingTo, undefined)
  assert.equal(readFileSync(join(base, "models", "m.gguf"), "utf8"), "weights")
  assert.deepEqual(readdirSync(join(drive, "SurfSense-Models")), [])
})

test("a failure partway leaves the old location in charge and the originals untouched", async () => {
  const base = install()
  const drive = temp()
  const p = await plan(base, "models", drive)
  // A name that cannot be read makes the copy fail once it has begun.
  const broken = { ...p, entries: [...p.entries, "no-such-folder"] }

  await assert.rejects(move(broken, base), (error: MoveFailedError) => error.reason === "failed")

  assert.equal(readStorageLocation(base).modelsRoot, undefined)
  assert.equal(readFileSync(join(base, "models", "m.gguf"), "utf8"), "weights")
  assert.deepEqual(readdirSync(join(drive, "SurfSense-Models")), [])
})

test("progress reaches every byte twice: the copy, then the check", async () => {
  const base = install()
  const big = Buffer.alloc(8 * 1024 * 1024, 1)
  writeFileSync(join(base, "models", "big.gguf"), big)
  const seen: string[] = []
  let last = { doneBytes: 0, totalBytes: 0 }

  await move(await plan(base, "models", temp()), base, new AbortController().signal, (progress) => {
    seen.push(progress.phase)
    last = progress
  })

  assert.equal(seen.at(-1), "switching")
  assert.equal(last.doneBytes, last.totalBytes)
  assert.ok(last.totalBytes >= big.length * 2)
})

test("moving back to the default folder undoes the move", async () => {
  const base = install()
  await move(await plan(base, "models", temp()), base)
  await removeOldCopies(base)
  const away = readStorageLocation(base).modelsRoot ?? ""

  await move(await plan(base, "models", null), base)
  await removeOldCopies(base)

  assert.equal(readStorageLocation(base).modelsRoot, undefined)
  assert.equal(readFileSync(join(base, "models", "m.gguf"), "utf8"), "weights")
  assert.equal(existsSync(away), false)
})

test("models leaving a moved data folder leave it reachable once the old copies go", async () => {
  const base = install()
  await move(await plan(base, "data", temp()), base)
  await removeOldCopies(base)

  await move(await plan(base, "models", temp()), base)
  await removeOldCopies(base)

  assert.equal(resolveStorage(base, readStorageLocation(base)).dataReachable, true)
})

test("models coming back into a moved data folder leave it reachable", async () => {
  const base = install()
  await move(await plan(base, "data", temp()), base)
  await removeOldCopies(base)
  await move(await plan(base, "models", temp()), base)
  await removeOldCopies(base)

  await move(await plan(base, "models", null), base)
  await removeOldCopies(base)

  const storage = resolveStorage(base, readStorageLocation(base))
  assert.equal(storage.modelsRoot, storage.dataRoot)
  assert.equal(storage.dataReachable, true)
  assert.equal(storage.modelsReachable, true)
})

test("all the data can come back to the default folder, models and all", async () => {
  const base = install()
  await move(await plan(base, "data", temp()), base)
  await removeOldCopies(base)

  await move(await plan(base, "data", null), base)
  await removeOldCopies(base)

  assert.equal(readStorageLocation(base).dataRoot, undefined)
  assert.equal(databaseValue(join(base, "surfsense.db")), "database")
  assert.equal(readFileSync(join(base, "models", "m.gguf"), "utf8"), "weights")
})

test("a folder already marked as models is switched to, and both copies are kept", async () => {
  const base = install()
  const drive = temp()
  const existing = join(drive, "SurfSense-Models")
  mkdirSync(join(existing, "models"), { recursive: true })
  writeFileSync(join(existing, "models", "other.gguf"), "from another install")
  writeMarker(existing, "models")

  const p = await plan(base, "models", drive)
  assert.equal(p.adopt, true)
  assert.equal(p.neededBytes, 0)
  await move(p, base)
  await removeOldCopies(base)

  assert.equal(readStorageLocation(base).modelsRoot, existing)
  assert.equal(readFileSync(join(existing, "models", "other.gguf"), "utf8"), "from another install")
  assert.equal(readFileSync(join(base, "models", "m.gguf"), "utf8"), "weights")
})

test("the app's folder with files and no marker is refused rather than merged into", async () => {
  const base = install()
  const drive = temp()
  mkdirSync(join(drive, "SurfSense-Models", "models"), { recursive: true })
  writeFileSync(join(drive, "SurfSense-Models", "models", "x.gguf"), "x")

  const result = await planMove({
    kind: "models",
    picked: drive,
    storage: resolveStorage(base, {}),
    appFolder: APP,
  })

  assert.deepEqual(result, { refused: "target_occupied" })
})

test("planning changes nothing: a picked folder that goes unused is not left behind", async () => {
  const base = install()
  const drive = temp()
  await plan(base, "models", drive)
  assert.deepEqual(readdirSync(drive), [])
  assert.equal(existsSync(join(base, LOCATION_FILE)), false)
})

test("a partial copy from a crash is found and removed at the next start", async () => {
  const base = install()
  const staging = join(temp(), ".incoming-models")
  mkdirSync(staging)
  writeFileSync(join(staging, "half.gguf"), "half")
  writeStorageLocation(base, { movingTo: staging })

  await removeInterruptedCopy(base)

  assert.equal(existsSync(staging), false)
  assert.equal(readStorageLocation(base).movingTo, undefined)
})

test("old copies on a drive that is away wait for a later start", async () => {
  const base = install()
  const away = join(temp(), "not-connected")
  writeStorageLocation(base, { leftBehind: [{ root: away, entries: ["models"] }] })

  await removeOldCopies(base)

  assert.deepEqual(readStorageLocation(base).leftBehind, [{ root: away, entries: ["models"] }])
})
