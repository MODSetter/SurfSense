// The instance's one password, scrypt-hashed on the volume (ADR 0074).
import { randomBytes, scrypt as scryptCallback, timingSafeEqual } from "node:crypto"
import { readFileSync, renameSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { promisify } from "node:util"

const scrypt = promisify(scryptCallback) as (
  password: string,
  salt: Buffer,
  length: number,
  options: { N: number; r: number; p: number; maxmem: number },
) => Promise<Buffer>

// OWASP's scrypt floor is N=2^17, r=8, p=1; it needs 128 MiB, so maxmem allows it.
const COST = { N: 2 ** 17, r: 8, p: 1, maxmem: 256 * 1024 * 1024 }
const LENGTH = 32
export const MIN_LENGTH = 8

/** Who set it: the app, or the server's setup (SURFSENSE_PASSWORD), which alone may change it. */
export type PasswordSource = "app" | "setup" // pragma: allowlist secret

export type PasswordRecord = {
  salt: string
  hash: string
  // Bumped on every change, so sessions signed for an older one stop working.
  version: number
  source: PasswordSource
}

function path(dataDir: string): string {
  return join(dataDir, "access.json")
}

export function readPassword(dataDir: string): PasswordRecord | null {
  try {
    const record = JSON.parse(readFileSync(path(dataDir), "utf8")) as PasswordRecord
    // Written before owners were kept: the setup's is set again at every start,
    // so one that stayed is the app's.
    return { ...record, source: record.source ?? "app" }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null
    throw error
  }
}

function write(dataDir: string, record: PasswordRecord) {
  // Written whole, then renamed: a crash leaves the old password, never half a new one.
  const temporary = `${path(dataDir)}.tmp`
  writeFileSync(temporary, JSON.stringify(record), { mode: 0o600 })
  renameSync(temporary, path(dataDir))
}

export async function setPassword(
  dataDir: string,
  password: string,
  source: PasswordSource = "app", // pragma: allowlist secret
): Promise<PasswordRecord> {
  const salt = randomBytes(16)
  const hash = await scrypt(password, salt, LENGTH, COST)
  const record: PasswordRecord = {
    salt: salt.toString("base64"),
    hash: hash.toString("base64"),
    version: (readPassword(dataDir)?.version ?? 0) + 1,
    source,
  }
  write(dataDir, record)
  return record
}

/** The setup stopped setting it: the password stays, now the app's to change. */
export function handOverToApp(dataDir: string) {
  const record = readPassword(dataDir)
  if (record?.source === "setup") write(dataDir, { ...record, source: "app" })
}

export async function checkPassword(record: PasswordRecord, password: string): Promise<boolean> {
  const hash = await scrypt(password, Buffer.from(record.salt, "base64"), LENGTH, COST)
  return timingSafeEqual(hash, Buffer.from(record.hash, "base64"))
}
