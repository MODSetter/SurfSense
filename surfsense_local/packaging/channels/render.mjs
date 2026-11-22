// Writes one package manager's files for a published desktop release:
//   node render.mjs <homebrew|winget|scoop|aur> --version <x.y.z> --out <dir> [--assets <release.json>]
// --assets is `gh api repos/MODSetter/SurfSense/releases/tags/v<x.y.z>`; without it the
// release is read from GitHub's API. Checksums are GitHub's asset digests, so no
// installer is downloaded. Everything is checked before anything is written.
import { mkdirSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { parseArgs } from "node:util"

import { aurPackage } from "./aur.mjs"
import { homebrewCask } from "./homebrew.mjs"
import { publishedRelease, readReleaseJson } from "./release.mjs"
import { scoopManifest } from "./scoop.mjs"
import { wingetManifests } from "./winget.mjs"

const CHANNELS = { homebrew: homebrewCask, winget: wingetManifests, scoop: scoopManifest, aur: aurPackage }
const USAGE = `usage: render.mjs <${Object.keys(CHANNELS).join("|")}> --version <x.y.z> --out <dir> [--assets <release.json>]`

/** Renders `channel`'s files for release v`version` into `out`; returns the paths written. */
export async function render({ channel, version, out, assets, env, fetch }) {
  const files = CHANNELS[channel](publishedRelease(await readReleaseJson({ version, file: assets, env, fetch }), version))
  return Object.entries(files).map(([path, text]) => {
    const target = join(out, path)
    mkdirSync(dirname(target), { recursive: true })
    writeFileSync(target, text)
    return target
  })
}

function parse(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: { version: { type: "string" }, out: { type: "string" }, assets: { type: "string" } },
  })
  const [channel, ...rest] = positionals
  if (!Object.hasOwn(CHANNELS, channel ?? "") || rest.length) throw new Error(USAGE)
  for (const name of ["version", "out"]) {
    if (!values[name]) throw new Error(`--${name} is required\n${USAGE}`)
  }
  // Desktop tags are vX.Y.Z (release-channels.yml), the one shape winget's YAML keeps a string.
  if (!/^\d+\.\d+\.\d+$/.test(values.version)) throw new Error(`--version must be X.Y.Z, not ${values.version}`)
  return { channel, ...values }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    for (const path of await render(parse(process.argv.slice(2)))) console.log(`wrote ${path}`)
  } catch (error) {
    console.error(`render.mjs: ${error.message}`)
    process.exitCode = 1
  }
}
