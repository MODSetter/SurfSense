import assert from "node:assert/strict"
import { generateKeyPairSync } from "node:crypto"
import test from "node:test"

import { checkManifestSignature, publicKeyFromHex, signManifest } from "./manifest-signature.ts"
import { UPDATE_PUBLIC_KEYS_HEX } from "./update-keys.ts"

/** A key pair made for this run; no private key lives in the repository. */
function keyPair() {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519")
  const x = publicKey.export({ format: "jwk" }).x as string
  return { privateKey, hex: Buffer.from(x, "base64url").toString("hex") }
}

const primary = keyPair()
const backup = keyPair()
const TRUSTED = [primary.hex, backup.hex]

// release.yml as electron-builder writes it.
const MANIFEST = Buffer.from(`version: 2.5.0
files:
  - url: SurfSense-Setup.exe
    sha512: c2hhNTEy
    size: 1234
path: SurfSense-Setup.exe
sha512: c2hhNTEy
releaseDate: '2026-12-01T10:00:00.000Z'
`)

test("a manifest the primary key signed gives back exactly the bytes that were signed", () => {
  const signed = signManifest(MANIFEST, "release.yml", primary.privateKey)

  assert.match(signed.toString(), /^surfsenseSignature: [A-Za-z0-9+/]{86}==\nversion: 2\.5\.0\n/)
  assert.deepEqual(checkManifestSignature(signed, "release.yml", TRUSTED), { body: MANIFEST })
})

test("the backup key's signature passes too, so a lost primary strands no one", () => {
  const signed = signManifest(MANIFEST, "release.yml", backup.privateKey)

  assert.deepEqual(checkManifestSignature(signed, "release.yml", TRUSTED), { body: MANIFEST })
})

test("a manifest with no signature line is refused", () => {
  assert.deepEqual(checkManifestSignature(MANIFEST, "release.yml", TRUSTED), {
    problem: "release.yml carries no SurfSense signature",
  })
})

test("a manifest signed by a key the app does not trust is refused", () => {
  const signed = signManifest(MANIFEST, "release.yml", keyPair().privateKey)

  assert.deepEqual(checkManifestSignature(signed, "release.yml", TRUSTED), {
    problem: "the signature on release.yml does not match",
  })
})

test("a manifest changed after it was signed is refused", () => {
  const signed = signManifest(MANIFEST, "release.yml", primary.privateKey).toString()

  for (const tampered of [
    signed.replace("version: 2.5.0", "version: 2.6.0"),
    signed.replace("sha512: c2hhNTEy\n    size", "sha512: ZXZpbA==\n    size"),
    `${signed}stagingPercentage: 100\n`,
    signed.replace(/\n$/, ""),
  ]) {
    assert.deepEqual(checkManifestSignature(Buffer.from(tampered), "release.yml", TRUSTED), {
      problem: "the signature on release.yml does not match",
    })
  }
})

test("a signature made for another platform's file does not pass for this one", () => {
  const signed = signManifest(MANIFEST, "release-mac.yml", primary.privateKey)

  assert.deepEqual(checkManifestSignature(signed, "release.yml", TRUSTED), {
    problem: "the signature on release.yml does not match",
  })
})

test("a signature line in any but its one exact form is refused", () => {
  const signed = signManifest(MANIFEST, "release.yml", primary.privateKey).toString()
  const [line, ...rest] = signed.split("\n")
  const body = rest.join("\n")

  for (const broken of [
    `${line}\r\n${body}`,
    `${line} \n${body}`,
    `${line!.replace("surfsenseSignature: ", "surfsenseSignature:  ")}\n${body}`,
    `${line!.slice(0, -4)}\n${body}`,
    line!,
  ]) {
    assert.deepEqual(checkManifestSignature(Buffer.from(broken), "release.yml", TRUSTED), {
      problem: "the signature on release.yml cannot be read",
    })
  }
  assert.deepEqual(checkManifestSignature(Buffer.from(`﻿${signed}`), "release.yml", TRUSTED), {
    problem: "release.yml carries no SurfSense signature",
  })
})

test("signing refuses a manifest that already carries a signature", () => {
  const signed = signManifest(MANIFEST, "release.yml", primary.privateKey)

  assert.throws(() => signManifest(signed, "release.yml", primary.privateKey), {
    message: "release.yml is already signed",
  })
})

test("the app trusts the maintainer's primary and backup keys, and nothing else", () => {
  // Changing either strands every app that shipped with the old list.
  assert.deepEqual(UPDATE_PUBLIC_KEYS_HEX, [
    "c6b2f835406fa5a43ada7c7bb91a3b2974633e22fe232ed7c6a91c430fb39d9e", // pragma: allowlist secret
    "0f7e78eb7fe998e1230a60e5849927c9de9ecd10470ac004b9212cc2be13c876", // pragma: allowlist secret
  ])
  // A key that does not load passes no manifest.
  for (const hex of UPDATE_PUBLIC_KEYS_HEX) {
    assert.equal(publicKeyFromHex(hex).asymmetricKeyType, "ed25519")
  }
})
