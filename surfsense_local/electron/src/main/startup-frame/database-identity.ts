import { createHash } from "node:crypto"
import { statSync } from "node:fs"
import { join } from "node:path"

/**
 * Names this data folder's database, so the page can tell a database it has
 * opened before from one made since: deleted and made again, it is a new one.
 * Hashed, so the page learns nothing about the disk. Null before it exists.
 */
export function databaseIdentity(dataDir: string): string | null {
  try {
    const { dev, ino, birthtimeMs } = statSync(join(dataDir, "surfsense.db"))
    return createHash("sha256")
      .update(`${dev}:${ino}:${birthtimeMs}`)
      .digest("hex")
      .slice(0, 32)
  } catch {
    return null
  }
}
