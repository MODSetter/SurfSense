// Licence texts a maintainer established for a package that ships none, each
// pinned to one version and naming where its terms were found.
import { readFileSync } from "node:fs"

export const REVIEWED_TEXTS = JSON.parse(readFileSync(new URL("./reviewed-texts.json", import.meta.url), "utf8"))

/** The fields a reviewed text supplies for `entry`, or none. */
export function reviewedText(reviewed, entry) {
  const match = reviewed.find((r) => r.tree === entry.tree && r.name === entry.name && r.version === entry.version)
  if (!match) return {}
  return { license: match.license, text: match.text, note: `Licence text supplied on review: ${match.source}` }
}
