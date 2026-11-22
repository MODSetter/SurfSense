import assert from "node:assert/strict"
import { existsSync, mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { loadSecret, type Cipher } from "./secret.ts"
import { isWindows } from "../../../sidecars/platform.ts"

// Reverses bytes so the file never holds the secret verbatim.
const cipher: Cipher = {
  encryptString: (plain: string) => Buffer.from(plain).reverse(),
  decryptString: (encrypted: Buffer) => Buffer.from(encrypted).reverse().toString(),
}

/** safeStorage while macOS refuses the keychain item: a denied prompt, or an app from a new team. */
const refused: Cipher = {
  encryptString: cipher.encryptString,
  decryptString: () => {
    throw new Error("Error while decrypting the ciphertext provided to safeStorage.decryptString.")
  },
}

/** safeStorage with no keychain at all this run: it can neither decrypt nor encrypt. */
const unavailable: Cipher = {
  decryptString: refused.decryptString,
  encryptString: () => {
    throw new Error("Error while encrypting the text provided to safeStorage.encryptString. Encryption is not available.")
  },
}

const ORIGINAL = "a".repeat(64)

function installWithSecret(): string {
  const path = join(mkdtempSync(join(tmpdir(), "secret-")), "secret.bin")
  writeFileSync(path, cipher.encryptString(ORIGINAL))
  return path
}

test("creates the secret once and reads the same one back", () => {
  const path = join(mkdtempSync(join(tmpdir(), "secret-")), "nested", "secret.bin")
  const first = loadSecret(path, cipher)
  assert.equal(first.length, 64)
  assert.equal(loadSecret(path, cipher), first)
  assert.ok(!readFileSync(path).includes(first))
  // Windows has no POSIX file mode.
  if (!isWindows) assert.equal(statSync(path).mode & 0o777, 0o600)
})

test("a secret the keychain refuses is set aside, not overwritten, and a new one starts the app", () => {
  const path = installWithSecret()
  const lines: string[] = []

  const minted = loadSecret(path, refused, (line) => lines.push(line))

  assert.equal(minted.length, 64)
  assert.notEqual(minted, ORIGINAL)
  assert.equal(cipher.decryptString(readFileSync(`${path}.unreadable`)), ORIGINAL)
  assert.equal(cipher.decryptString(readFileSync(path)), minted)
  assert.match(lines.join("\n"), /kept as .*secret\.bin\.unreadable/)
})

test("once the keychain opens it again, the original secret comes back", () => {
  const path = installWithSecret()
  loadSecret(path, refused)

  assert.equal(loadSecret(path, cipher), ORIGINAL)
  assert.equal(existsSync(`${path}.unreadable`), false)
  assert.equal(loadSecret(path, cipher), ORIGINAL)
})

test("while the keychain still refuses it, every launch keeps the original aside", () => {
  const path = installWithSecret()
  loadSecret(path, refused)
  loadSecret(path, refused)
  loadSecret(path, refused)

  assert.equal(cipher.decryptString(readFileSync(`${path}.unreadable`)), ORIGINAL)
  assert.equal(loadSecret(path, cipher), ORIGINAL)
})

test("a launch that can open only the new secret uses it and keeps trying the original", () => {
  const path = installWithSecret()
  const minted = loadSecret(path, refused)
  // The keychain item was reset: the new secret opens, the original never will.
  const onlyMinted: Cipher = {
    encryptString: cipher.encryptString,
    decryptString: (encrypted) => {
      const plain = cipher.decryptString(encrypted)
      if (plain === ORIGINAL) throw new Error("wrong key")
      return plain
    },
  }

  assert.equal(loadSecret(path, onlyMinted), minted)
  assert.equal(loadSecret(path, onlyMinted), minted)
  assert.equal(cipher.decryptString(readFileSync(`${path}.unreadable`)), ORIGINAL)
})

test("with no keychain at all, the app starts on a secret for this run and leaves the original alone", () => {
  const path = installWithSecret()

  const forNow = loadSecret(path, unavailable)

  assert.equal(forNow.length, 64)
  assert.equal(existsSync(path), false)
  assert.equal(cipher.decryptString(readFileSync(`${path}.unreadable`)), ORIGINAL)
  assert.equal(loadSecret(path, cipher), ORIGINAL)
})
