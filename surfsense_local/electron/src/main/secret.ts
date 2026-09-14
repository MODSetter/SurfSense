import { randomBytes } from "node:crypto"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { dirname } from "node:path"

export type Cipher = {
  encryptString(plain: string): Buffer
  decryptString(encrypted: Buffer): string
}

/** Per-install secret the sidecars encrypt API keys with, kept under the OS keychain. */
export function loadSecret(path: string, cipher: Cipher): string {
  try {
    return cipher.decryptString(readFileSync(path))
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error
  }
  const secret = randomBytes(32).toString("hex")
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, cipher.encryptString(secret), { mode: 0o600 })
  return secret
}
