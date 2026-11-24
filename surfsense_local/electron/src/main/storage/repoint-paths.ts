import { existsSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"

const posixForm = (path: string): string => path.replaceAll("\\", "/")

/**
 * Each spelling a folder is stored under, with its separator, so `/a/b` cannot
 * match `/a/b-other`. opencode and Claude Code store it as written, inside JSON,
 * and audio.cpp's configs with forward slashes.
 */
function spellings(oldRoot: string, newRoot: string): Array<[string, string]> {
  const pairs = new Map<string, string>()
  const add = (from: string, to: string, separator: string) =>
    pairs.set(`${from}${separator}`, `${to}${separator}`)
  const escaped = (path: string) => JSON.stringify(path).slice(1, -1)
  // Python's json.dumps writes a non-ASCII folder name as \uXXXX.
  const ascii = (text: string) =>
    text.replace(/[^\x00-\x7f]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`)
  const windows = oldRoot.includes("\\")
  add(ascii(escaped(posixForm(oldRoot))), ascii(escaped(posixForm(newRoot))), "/")
  add(posixForm(oldRoot), posixForm(newRoot), "/")
  if (windows) {
    add(oldRoot, newRoot, "\\")
    add(escaped(oldRoot), escaped(newRoot), "\\\\")
    add(ascii(escaped(oldRoot)), ascii(escaped(newRoot)), "\\\\")
  }
  return [...pairs]
}

function repointedString(value: string, oldRoot: string, newRoot: string): string {
  const from = `${posixForm(oldRoot)}/`
  return value.startsWith(from) ? `${posixForm(newRoot)}/${value.slice(from.length)}` : value
}

function repointedJson(value: unknown, oldRoot: string, newRoot: string): unknown {
  if (typeof value === "string") return repointedString(value, oldRoot, newRoot)
  if (Array.isArray(value)) return value.map((item) => repointedJson(item, oldRoot, newRoot))
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, repointedJson(item, oldRoot, newRoot)]),
    )
  }
  return value
}

// Names from write_server_config and write_transcription_config.
const AUDIO_CONFIGS = ["server.json", "transcription.json"]

/** The configs that name their models by absolute path, in the copy, before it goes live. */
export function repointModelConfigs(stagingRoot: string, oldRoot: string, newRoot: string): void {
  for (const name of AUDIO_CONFIGS) {
    const path = join(stagingRoot, "audio", name)
    if (!existsSync(path)) continue
    const repointed = repointedJson(JSON.parse(readFileSync(path, "utf8")), oldRoot, newRoot)
    writeFileSync(`${path}.tmp`, `${JSON.stringify(repointed, null, 2)}\n`)
    renameSync(`${path}.tmp`, path)
  }
  // The API writes it again at startup from what it finds; a stale one names files that moved.
  rmSync(join(stagingRoot, "models", "models.ini"), { force: true })
}

function replaceInColumns(db: DatabaseSync, table: string, pairs: Array<[string, string]>): void {
  const columns = db.prepare(`PRAGMA table_info("${table}")`).all() as Array<{ name: string }>
  for (const { name } of columns) {
    for (const [from, to] of pairs) {
      db.prepare(
        `UPDATE "${table}" SET "${name}" = replace("${name}", ?, ?)
         WHERE typeof("${name}") = 'text' AND instr("${name}", ?) > 0`,
      ).run(from, to, from)
    }
  }
}

function repointDatabase(
  path: string,
  pairs: Array<[string, string]>,
  tablesOf: (db: DatabaseSync) => string[],
): void {
  if (!existsSync(path)) return
  const db = new DatabaseSync(path)
  try {
    db.exec("PRAGMA wal_checkpoint(TRUNCATE)")
    db.exec("BEGIN")
    for (const table of tablesOf(db)) replaceInColumns(db, table, pairs)
    db.exec("COMMIT")
    db.exec("PRAGMA wal_checkpoint(TRUNCATE)")
  } finally {
    db.close()
  }
}

const everyTable = (db: DatabaseSync): string[] =>
  (
    db
      .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
      .all() as Array<{ name: string }>
  ).map(({ name }) => name)

/**
 * opencode runs every call about a session in the folder it stored: without this
 * each thread reads as legacy after a move (measured on opencode 2.1.2). In
 * SurfSense's own database only the transcripts: a document may quote any path.
 */
export function repointDatabases(stagingRoot: string, oldRoot: string, newRoot: string): void {
  const pairs = spellings(oldRoot, newRoot)
  repointDatabase(join(stagingRoot, "agent", "opencode", "data", "opencode", "opencode.db"), pairs, everyTable)
  repointDatabase(join(stagingRoot, "surfsense.db"), pairs, (db) =>
    everyTable(db).filter((name) => name === "claude_session_entries"),
  )
}
