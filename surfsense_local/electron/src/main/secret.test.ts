import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"

import { loadSecret } from "./secret.ts"

// Reverses bytes so the file never holds the secret verbatim.
const cipher = {
  encryptString: (plain: string) => Buffer.from(plain).reverse(),
  decryptString: (encrypted: Buffer) => Buffer.from(encrypted).reverse().toString(),
}

test("creates the secret once and reads the same one back", () => {
  const path = join(mkdtempSync(join(tmpdir(), "secret-")), "nested", "secret.bin")
  const first = loadSecret(path, cipher)
  assert.equal(first.length, 64)
  assert.equal(loadSecret(path, cipher), first)
  assert.ok(!readFileSync(path).includes(first))
  assert.equal(statSync(path).mode & 0o777, 0o600)
})

test("mints a new secret when safeStorage cannot decrypt the file", () => {
  const path = join(mkdtempSync(join(tmpdir(), "secret-")), "secret.bin")
  writeFileSync(path, cipher.encryptString("a".repeat(64)))
  const stale = {
    encryptString: cipher.encryptString,
    decryptString: () => {
      throw new Error(
        "Error while decrypting the ciphertext provided to safeStorage.decryptString."
      )
    },
  }
  const minted = loadSecret(path, stale)
  assert.equal(minted.length, 64)
  assert.notEqual(minted, "a".repeat(64))
  assert.equal(loadSecret(path, cipher), minted)
})
