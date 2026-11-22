import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { generateKeyPairSync } from "node:crypto"
import { mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

import { checkManifestSignature } from "../../src/main/update-feed/manifest-signature.ts"
import { signedManifest } from "./sign-manifest.mjs"

const SCRIPT = fileURLToPath(new URL("./sign-manifest.mjs", import.meta.url))
const MANIFEST = Buffer.from("version: 2.5.0\nfiles:\n  - url: SurfSense-arm64.zip\n    sha512: c2hhNTEy\n    size: 1\n")

function testKey() {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519")
  return {
    pem: privateKey.export({ format: "pem", type: "pkcs8" }),
    hex: Buffer.from(publicKey.export({ format: "jwk" }).x, "base64url").toString("hex"),
  }
}

test("a manifest signed with a key the app trusts passes the app's own check", () => {
  const key = testKey()

  const signed = signedManifest(MANIFEST, "release-mac.yml", key.pem, [key.hex])

  assert.deepEqual(checkManifestSignature(signed, "release-mac.yml", [key.hex]), { body: MANIFEST })
})

test("a signing key the app does not compile in stops the release", () => {
  // The shipped keys, as CI uses them: a stray test key is not among them.
  assert.throws(() => signedManifest(MANIFEST, "release-mac.yml", testKey().pem), {
    message: "UPDATE_SIGNING_KEY is not a key the app trusts (the signature on release-mac.yml does not match)",
  })
})

test("a missing secret, an empty manifest or another file name is refused", () => {
  const key = testKey()
  assert.throws(() => signedManifest(MANIFEST, "release.yml", "", [key.hex]), /UPDATE_SIGNING_KEY is empty/)
  assert.throws(() => signedManifest(Buffer.alloc(0), "release.yml", key.pem, [key.hex]), /is empty/)
  assert.throws(() => signedManifest(MANIFEST, "stable.yml", key.pem, [key.hex]), /not a release\*\.yml name/)
})

test("run as CI runs it, with a key the app does not trust, it writes nothing and exits non-zero", () => {
  const dir = mkdtempSync(join(tmpdir(), "sign-manifest-"))
  writeFileSync(join(dir, "stable.yml"), MANIFEST)

  assert.throws(
    () =>
      execFileSync(
        process.execPath,
        ["--disable-warning=MODULE_TYPELESS_PACKAGE_JSON", SCRIPT, join(dir, "stable.yml"), join(dir, "release.yml")], // pragma: allowlist secret
        { env: { ...process.env, UPDATE_SIGNING_KEY: testKey().pem }, stdio: "pipe" }
      ),
    (error) => /not a key the app trusts/.test(String(error.stderr))
  )
})
