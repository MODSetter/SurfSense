import { randomBytes } from "node:crypto"
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
import { dirname } from "node:path"

export type Cipher = {
  encryptString(plain: string): Buffer
  decryptString(encrypted: Buffer): string
}

/**
 * Per-install secret the sidecars encrypt API keys with, kept under the OS keychain.
 * A file the keychain refuses (a denied prompt, a new signing team) is set aside and
 * tried at every launch, never overwritten, so the keys saved with it come back.
 */
export function loadSecret(
  path: string,
  cipher: Cipher,
  warn: (line: string) => void = () => undefined
): string {
  const aside = `${path}.unreadable`
  const earlier = opened(aside, cipher)
  if (earlier !== null) {
    renameSync(aside, path)
    warn("the keychain opened the secret it had refused, so the API keys saved with it work again")
    return earlier
  }
  const current = opened(path, cipher)
  if (current !== null) return current
  // Only the first refused file is kept: it holds every key saved before the refusal.
  if (existsSync(path) && !existsSync(aside)) {
    renameSync(path, aside)
    warn(`the keychain would not open ${path}; it is kept as ${aside} and tried again at the next launch`)
  }
  // Refusing to boot is worse: API keys saved from now on use a new secret.
  const secret = randomBytes(32).toString("hex")
  let sealed: Buffer
  try {
    sealed = cipher.encryptString(secret)
  } catch (error) {
    warn(`the keychain cannot encrypt, so this run's secret is kept in memory only: ${String(error)}`)
    return secret
  }
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, sealed, { mode: 0o600 })
  return secret
}

function opened(path: string, cipher: Cipher): string | null {
  let sealed: Buffer
  try {
    sealed = readFileSync(path)
  } catch {
    return null
  }
  try {
    return cipher.decryptString(sealed)
  } catch {
    return null
  }
}
