import { createPublicKey, sign, verify, type KeyObject } from "node:crypto"

// A signed release*.yml (contract 05 part A) is `surfsenseSignature: <base64>`,
// then the manifest exactly as electron-builder wrote it. The domain and the file's
// name are signed too, so a signature made for anything else never passes here.
const FIELD = "surfsenseSignature: "
const DOMAIN = "surfsense-update-manifest/1\n"
const SIGNATURE_BYTES = 64

export type CheckedManifest = { body: Buffer } | { problem: string }

/** The bytes a manifest's signature covers. */
export function signedPayload(channelFile: string, body: Buffer): Buffer {
  return Buffer.concat([Buffer.from(`${DOMAIN}${channelFile}\n`, "utf8"), body])
}

export function publicKeyFromHex(hex: string): KeyObject {
  if (!/^[0-9a-f]{64}$/.test(hex)) throw new Error("not a 32-byte Ed25519 public key in hex")
  return createPublicKey({
    key: { kty: "OKP", crv: "Ed25519", x: Buffer.from(hex, "hex").toString("base64url") },
    format: "jwk",
  })
}

/**
 * The manifest after its signature line, when one of `trustedKeys` signed it
 * under this name; else why it is refused. Nothing before the body is parsed.
 */
export function checkManifestSignature(
  file: Buffer,
  channelFile: string,
  trustedKeys: readonly string[]
): CheckedManifest {
  if (file.subarray(0, FIELD.length).toString("latin1") !== FIELD) {
    return { problem: `${channelFile} carries no SurfSense signature` }
  }
  const end = file.indexOf(0x0a)
  const encoded = file.subarray(FIELD.length, end === -1 ? file.length : end).toString("latin1")
  const signature = Buffer.from(encoded, "base64")
  // Only the canonical encoding: Buffer.from skips characters base64 does not have.
  if (end === -1 || signature.length !== SIGNATURE_BYTES || signature.toString("base64") !== encoded) {
    return { problem: `the signature on ${channelFile} cannot be read` }
  }
  const body = file.subarray(end + 1)
  const payload = signedPayload(channelFile, body)
  const signed = trustedKeys.some((hex) => {
    try {
      return verify(null, payload, publicKeyFromHex(hex), signature)
    } catch {
      return false
    }
  })
  return signed ? { body } : { problem: `the signature on ${channelFile} does not match` }
}

/** `file` with its signature line in front, signed with `privateKey` as `channelFile`. */
export function signManifest(file: Buffer, channelFile: string, privateKey: KeyObject): Buffer {
  if (file.subarray(0, FIELD.length).toString("latin1") === FIELD) {
    throw new Error(`${channelFile} is already signed`)
  }
  if (privateKey.asymmetricKeyType !== "ed25519") throw new Error("the signing key is not Ed25519")
  const signature = sign(null, signedPayload(channelFile, file), privateKey).toString("base64")
  return Buffer.concat([Buffer.from(`${FIELD}${signature}\n`, "utf8"), file])
}
