// Writes SHA256SUMS for a draft release from the digests GitHub keeps per asset, so no
// installer is downloaded again to hash it.
//   node write-sha256sums.mjs --releases <releases.json> --tag <vX.Y.Z> --out <SHA256SUMS>
// releases.json is `gh api --paginate --slurp repos/<repo>/releases`: a draft is not
// served at /releases/tags/<tag>.
import { readFileSync, writeFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { parseArgs } from "node:util"

const SUMS = "SHA256SUMS"
const DIGEST = /^sha256:([0-9a-f]{64})$/

/** The one draft tagged `tag`, from a list of releases or from `--slurp`ed pages of one. */
export function findDraft(releases, tag) {
  const drafts = releases.flat().filter((release) => release.draft && release.tag_name === tag)
  if (drafts.length === 1) return drafts[0]
  if (!drafts.length) throw new Error(`no draft release is tagged ${tag}`)
  throw new Error(`${drafts.length} draft releases are tagged ${tag}; delete the stray one`)
}

/** `sha256sum` lines for every asset but SHA256SUMS, in byte order of name as `LC_ALL=C sort` gives. */
export function sha256sums(release) {
  const assets = release.assets
    .filter((asset) => asset.name !== SUMS)
    .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
  if (!assets.length) throw new Error(`${release.tag_name} has no assets to list`)
  return assets
    .map(({ name, digest }) => {
      const hex = DIGEST.exec(digest ?? "")?.[1]
      if (!hex) throw new Error(`${name} has no sha256 digest (${digest}); re-run once its upload has finished`)
      return `${hex}  ${name}\n`
    })
    .join("")
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { values } = parseArgs({
    options: { releases: { type: "string" }, tag: { type: "string" }, out: { type: "string" } },
  })
  for (const name of ["releases", "tag", "out"]) {
    if (!values[name]) throw new Error(`--${name} is required`)
  }
  const release = findDraft(JSON.parse(readFileSync(values.releases, "utf8")), values.tag)
  writeFileSync(values.out, sha256sums(release))
}
