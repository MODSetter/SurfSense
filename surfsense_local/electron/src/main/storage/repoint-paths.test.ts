import assert from "node:assert/strict"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"
import test from "node:test"

import { repointDatabases, repointModelConfigs } from "./repoint-paths.ts"

const temp = () => mkdtempSync(join(tmpdir(), "surfsense-repoint-"))

test("a voice's config follows the move, and the llama.cpp preset goes for the API to rewrite", () => {
  const staging = temp()
  mkdirSync(join(staging, "audio"))
  mkdirSync(join(staging, "models"))
  writeFileSync(
    join(staging, "audio", "server.json"),
    JSON.stringify({ models: [{ id: "k", path: "/old/root/audio/k", session_options: { "k.espeak_data_path": "/app/espeak" } }] }),
  )
  writeFileSync(join(staging, "models", "models.ini"), "[a]\nmodel = /old/root/models/a.gguf\n")

  repointModelConfigs(staging, "/old/root", "/new/some root")

  const config = JSON.parse(readFileSync(join(staging, "audio", "server.json"), "utf8"))
  assert.equal(config.models[0].path, "/new/some root/audio/k")
  assert.equal(config.models[0].session_options["k.espeak_data_path"], "/app/espeak")
  assert.equal(existsSync(join(staging, "models", "models.ini")), false)
})

test("a Windows config names its folders with forward slashes, and still follows", () => {
  const staging = temp()
  mkdirSync(join(staging, "audio"))
  writeFileSync(join(staging, "audio", "server.json"), JSON.stringify({ models: [{ path: "C:/Users/me/.surfsense/audio/k" }] }))

  repointModelConfigs(staging, "C:\\Users\\me\\.surfsense", "D:\\SurfSense-Models")

  const config = JSON.parse(readFileSync(join(staging, "audio", "server.json"), "utf8"))
  assert.equal(config.models[0].path, "D:/SurfSense-Models/audio/k")
})

test("a sibling folder with the same prefix is not this one", () => {
  const staging = temp()
  mkdirSync(join(staging, "audio"))
  writeFileSync(join(staging, "audio", "server.json"), JSON.stringify({ models: [{ path: "/old/root-other/audio/k" }] }))

  repointModelConfigs(staging, "/old/root", "/new")

  const config = JSON.parse(readFileSync(join(staging, "audio", "server.json"), "utf8"))
  assert.equal(config.models[0].path, "/old/root-other/audio/k")
})

function opencodeDatabase(staging: string): string {
  const folder = join(staging, "agent", "opencode", "data", "opencode")
  mkdirSync(folder, { recursive: true })
  const path = join(folder, "opencode.db")
  const db = new DatabaseSync(path)
  db.exec("PRAGMA journal_mode=WAL; CREATE TABLE session (id TEXT, directory TEXT, data BLOB, n INTEGER)")
  db.prepare("INSERT INTO session VALUES (?,?,?,?)").run("s1", "/old/root/data/workspaces/1/agent/threads/5", Buffer.from("/old/root/x"), 1)
  db.prepare("INSERT INTO session VALUES (?,?,?,?)").run("s2", "/old/root-other/kept", null, 2)
  db.close()
  return path
}

test("opencode's sessions follow the folder they work in", () => {
  const staging = temp()
  const path = opencodeDatabase(staging)

  repointDatabases(staging, "/old/root", "/new root")

  const db = new DatabaseSync(path)
  const rows = db.prepare("SELECT id, directory, data, n FROM session ORDER BY id").all() as Array<Record<string, unknown>>
  db.close()
  assert.equal(rows[0]?.directory, "/new root/data/workspaces/1/agent/threads/5")
  assert.equal(rows[1]?.directory, "/old/root-other/kept")
  assert.equal(Buffer.from(rows[0]?.data as Uint8Array).toString(), "/old/root/x")
  assert.equal(rows[0]?.n, 1)
})

test("in SurfSense's database only the agent's transcripts change: a user's text is theirs", () => {
  const staging = temp()
  const path = join(staging, "surfsense.db")
  const db = new DatabaseSync(path)
  db.exec("CREATE TABLE claude_session_entries (entry TEXT); CREATE TABLE documents (content TEXT)")
  db.prepare("INSERT INTO claude_session_entries VALUES (?)").run('{"cwd":"/old/root/data/t"}')
  db.prepare("INSERT INTO documents VALUES (?)").run("my notes mention /old/root/data/t")
  db.close()

  repointDatabases(staging, "/old/root", "/new")

  const after = new DatabaseSync(path)
  assert.deepEqual({ ...after.prepare("SELECT entry FROM claude_session_entries").get() }, { entry: '{"cwd":"/new/data/t"}' })
  assert.deepEqual({ ...after.prepare("SELECT content FROM documents").get() }, { content: "my notes mention /old/root/data/t" })
  after.close()
})

test("a path written into JSON on Windows is found under its escaped spelling", () => {
  const staging = temp()
  const path = join(staging, "surfsense.db")
  const db = new DatabaseSync(path)
  db.exec("CREATE TABLE claude_session_entries (entry TEXT)")
  db.prepare("INSERT INTO claude_session_entries VALUES (?)").run(JSON.stringify({ cwd: "C:\\old\\root\\data" }))
  db.close()

  repointDatabases(staging, "C:\\old\\root", "D:\\new")

  const after = new DatabaseSync(path)
  const row = after.prepare("SELECT entry FROM claude_session_entries").get() as { entry: string }
  after.close()
  assert.equal(JSON.parse(row.entry).cwd, "D:\\new\\data")
})

test("a non-English folder name written by Python as \\uXXXX is found too", () => {
  const staging = temp()
  const path = join(staging, "surfsense.db")
  const db = new DatabaseSync(path)
  db.exec("CREATE TABLE claude_session_entries (entry TEXT)")
  db.prepare("INSERT INTO claude_session_entries VALUES (?)").run(String.raw`{"cwd":"/home/\u00fcser/.surfsense/data"}`)
  db.close()

  repointDatabases(staging, "/home/üser/.surfsense", "/mnt/nëw")

  const after = new DatabaseSync(path)
  const row = after.prepare("SELECT entry FROM claude_session_entries").get() as { entry: string }
  after.close()
  assert.equal(JSON.parse(row.entry).cwd, "/mnt/nëw/data")
})

test("no database yet is nothing to do", () => {
  repointDatabases(temp(), "/old", "/new")
})
