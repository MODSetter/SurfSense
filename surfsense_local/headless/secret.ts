/**
 * The install's secret, settled before any Python starts: the API and three
 * workers would otherwise race to create the file the backend falls back to
 * (shared/secrets.py). Same file and format as that fallback.
 */
import { randomBytes } from "node:crypto"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"

export function resolveSecret(env: Record<string, string | undefined>, dataDir: string): string {
  if (env.SURFSENSE_LOCAL_SECRET) return env.SURFSENSE_LOCAL_SECRET
  const path = join(dataDir, "secret")
  mkdirSync(dataDir, { recursive: true })
  try {
    writeFileSync(path, randomBytes(32).toString("hex"), { flag: "wx", mode: 0o600 })
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error
  }
  const secret = readFileSync(path, "utf8").trim()
  // A new one would make every stored provider key unreadable.
  if (!secret) throw new Error(`${path} is empty; restore the install's secret or remove the file`)
  return secret
}
