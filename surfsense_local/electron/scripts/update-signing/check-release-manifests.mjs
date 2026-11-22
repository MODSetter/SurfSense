// The update half of the publish gate (ADR 0091, RELEASE.md): every manifest a
// release carries, checked on the draft before it is undrafted, since publishing
// makes it Latest and every installed generation reads its file off it at once.
//   node scripts/update-signing/check-release-manifests.mjs <dir> --version 2.5.0 --handover 2.4.0 \
//     [--windows-carried] [--legacy] [--handover-assets]
// <dir> holds the release's manifests. --windows-carried: this release has no
// signed Windows build and carries an earlier release.yml forward. --legacy: the
// legacy bridge's latest*.yml must be there too (a tag's run). --handover-assets:
// download the handover release's installers and compare them with the frozen
// manifests, as an app before 2.4.0 will.
import { createHash } from "node:crypto"
import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { parseArgs } from "node:util"
import { fileURLToPath } from "node:url"

import { parseUpdateInfo } from "electron-updater/out/providers/Provider.js"

import { githubReleaseDownload } from "../../src/main/update-feed/feed-addresses.ts"
import { githubManifestProblem } from "../../src/main/update-feed/manifest-checks.ts"
import { checkManifestSignature } from "../../src/main/update-feed/manifest-signature.ts"
import { UPDATE_PUBLIC_KEYS_HEX } from "../../src/main/update-feed/update-keys.ts"

const PLATFORMS = ["", "-mac", "-linux"]
const LEGACY_VERSION = "0.0.40"

/** -1, 0 or 1, for X.Y.Z versions. */
export function compareVersions(a, b) {
  const [x, y] = [a, b].map((version) => version.split(".").map(Number))
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1
  return 0
}

/** The release's update path: the handover itself, or a release after it. */
export function updatePath(version, handover) {
  const order = compareVersions(version, handover)
  return order === 0 ? "handover" : order > 0 ? "after" : "before"
}

function parsed(name, text) {
  try {
    const info = parseUpdateInfo(text, name, new URL(`https://example.invalid/${name}`))
    return githubManifestProblem(info) === null ? info : null
  } catch {
    return null
  }
}

/** Every problem with the manifests in `dir`, or none. */
export function manifestProblems(dir, options) {
  const { version, handover, windowsCarried = false, legacy = false, trustedKeys = UPDATE_PUBLIC_KEYS_HEX } = options
  const problems = []
  const path = updatePath(version, handover)
  if (path === "before") return [`${version} is before the handover release ${handover}: it carries no release*.yml`]
  if (path === "handover" && windowsCarried) problems.push("the handover release must carry its own signed Windows build")
  const read = (name) => (existsSync(join(dir, name)) ? readFileSync(join(dir, name)) : null)

  const bodies = {}
  for (const platform of PLATFORMS) {
    const name = `release${platform}.yml`
    const file = read(name)
    if (file === null) {
      problems.push(`${name} is missing`)
      continue
    }
    const checked = checkManifestSignature(file, name, trustedKeys)
    if ("problem" in checked) {
      problems.push(checked.problem)
      continue
    }
    bodies[platform] = checked.body
    const info = parsed(name, checked.body.toString("utf8"))
    if (info === null) {
      problems.push(`${name} is signed but not a manifest the app can use`)
    } else if (platform === "" && windowsCarried) {
      if (compareVersions(info.version, version) >= 0) {
        problems.push(`release.yml carried forward names ${info.version}, not an earlier signed Windows build`)
      }
    } else if (info.version !== version) {
      problems.push(`${name} names ${info.version}, not ${version}`)
    }
  }

  for (const platform of PLATFORMS) {
    const name = `stable${platform}.yml`
    const file = read(name)
    if (file === null) {
      problems.push(`${name} is missing`)
      continue
    }
    if (path === "handover") {
      // The signed copies are these files, byte for byte.
      if (bodies[platform] && !file.equals(bodies[platform])) problems.push(`release${platform}.yml is not ${name} signed`)
      continue
    }
    if (platform === "-linux") {
      // Linux checks no signature, so apps before 2.4.0 go straight to this release.
      if (bodies[platform] && !file.equals(bodies[platform])) problems.push("stable-linux.yml is not this release's own release-linux.yml")
      continue
    }
    const tag = `tag: v${handover}\n`
    const text = file.toString("utf8")
    if (!text.startsWith(tag)) problems.push(`${name} does not start with "${tag.trim()}"`)
    const info = parsed(name, text.startsWith(tag) ? text.slice(tag.length) : text)
    if (info?.version !== handover) problems.push(`${name} does not name the handover release ${handover}`)
  }

  if (legacy) {
    for (const name of ["latest.yml", "latest-mac.yml", "latest-linux.yml"]) {
      const text = read(name)?.toString("utf8")
      if (text === undefined) problems.push(`${name} is missing: every legacy 0.0.x check would 404`)
      else if (!text.startsWith(`tag: v${LEGACY_VERSION}\n`) || !text.includes(`\nversion: ${LEGACY_VERSION}\n`)) {
        problems.push(`${name} does not send legacy apps to v${LEGACY_VERSION}`)
      }
    }
  }
  return problems
}

async function digest(url, fetchFrom) {
  const response = await fetchFrom(url, { redirect: "follow" })
  if (response.status !== 200 || !response.body) throw new Error(`HTTP ${response.status}`)
  const hash = createHash("sha512")
  let size = 0
  for await (const chunk of response.body) {
    hash.update(chunk)
    size += chunk.length
  }
  return { sha512: hash.digest("base64"), size }
}

/**
 * The frozen stable.yml and stable-mac.yml against the handover release's own
 * files: an app before 2.4.0 downloads each and refuses one whose sha512 differs.
 */
export async function handoverAssetProblems(dir, handover, options = {}) {
  const { fetch: fetchFrom = fetch, releaseDownload = githubReleaseDownload } = options
  const problems = []
  const tag = `tag: v${handover}\n`
  for (const name of ["stable.yml", "stable-mac.yml"]) {
    const text = readFileSync(join(dir, name), "utf8")
    const info = parsed(name, text.startsWith(tag) ? text.slice(tag.length) : text)
    if (info === null) {
      problems.push(`${name} cannot be read`)
      continue
    }
    for (const file of info.files) {
      const url = new URL(file.url, releaseDownload(handover)).href
      try {
        const served = await digest(url, fetchFrom)
        if (served.sha512 !== file.sha512 || served.size !== file.size) {
          problems.push(`${url} is not the file ${name} names: its sha512 or size changed`)
        }
      } catch (error) {
        problems.push(`${url} could not be read (${error.message})`)
      }
    }
  }
  return problems
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const { positionals, values } = parseArgs({
    allowPositionals: true,
    options: {
      version: { type: "string" },
      handover: { type: "string" },
      "windows-carried": { type: "boolean", default: false },
      legacy: { type: "boolean", default: false },
      "handover-assets": { type: "boolean", default: false },
    },
  })
  const [dir] = positionals
  if (!dir || !values.version || !values.handover) {
    throw new Error("usage: check-release-manifests.mjs <dir> --version X.Y.Z --handover X.Y.Z [...]")
  }
  const problems = manifestProblems(dir, {
    version: values.version,
    handover: values.handover,
    windowsCarried: values["windows-carried"],
    legacy: values.legacy,
  })
  if (values["handover-assets"] && updatePath(values.version, values.handover) === "after") {
    problems.push(...(await handoverAssetProblems(dir, values.handover)))
  }
  for (const problem of problems) console.error(`::error::${problem}`)
  if (problems.length) process.exit(1)
  console.log(`every update manifest for ${values.version} is in place and signed`)
}
