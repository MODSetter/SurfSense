// Signs one update manifest as a release*.yml with the key in UPDATE_SIGNING_KEY
// (ADR 0091), and fails unless the result passes the app's own check against the
// keys it compiles in, so a wrong secret stops the release, not every update:
//   UPDATE_SIGNING_KEY="$(cat key.pem)" node scripts/update-signing/sign-manifest.mjs <source.yml> <out/release*.yml>
// The output's file name is the name the signature binds.
import { createPrivateKey } from "node:crypto"
import { readFileSync, writeFileSync } from "node:fs"
import { basename } from "node:path"
import { fileURLToPath } from "node:url"

import { checkManifestSignature, signManifest } from "../../src/main/update-feed/manifest-signature.ts"
import { UPDATE_PUBLIC_KEYS_HEX } from "../../src/main/update-feed/update-keys.ts"

const RELEASE_MANIFEST = /^release(-mac|-linux(-arm64)?)?\.yml$/

export function signedManifest(source, channelFile, pem, trustedKeys = UPDATE_PUBLIC_KEYS_HEX) {
  if (!RELEASE_MANIFEST.test(channelFile)) throw new Error(`${channelFile} is not a release*.yml name`)
  if (source.length === 0) throw new Error(`the manifest for ${channelFile} is empty`)
  if (!pem?.trim()) throw new Error("UPDATE_SIGNING_KEY is empty: set the repository secret (surfsense_local/RELEASE.md)")
  const signed = signManifest(source, channelFile, createPrivateKey(pem))
  const checked = checkManifestSignature(signed, channelFile, trustedKeys)
  if ("problem" in checked) {
    throw new Error(`UPDATE_SIGNING_KEY is not a key the app trusts (${checked.problem})`)
  }
  return signed
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const [source, out] = process.argv.slice(2)
  if (!source || !out) throw new Error("usage: sign-manifest.mjs <source.yml> <out/release*.yml>")
  writeFileSync(out, signedManifest(readFileSync(source), basename(out), process.env.UPDATE_SIGNING_KEY))
  console.log(`signed ${out} from ${source}`)
}
