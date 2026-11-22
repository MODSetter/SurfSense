// Fails unless the packaged Windows app's app-update.yml names a publisher:
// without one NsisUpdater skips the signature check altogether, the app's own
// verifier included (src/main/installer-signature/, ADR 0091).
//   node scripts/update-signing/check-publisher-name.mjs release/win-unpacked/resources/app-update.yml
import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"

// The YAML reader electron-updater reads app-update.yml with.
const updater = createRequire(createRequire(import.meta.url).resolve("electron-updater"))
const { load } = updater("js-yaml")

export function publisherNameProblem(text) {
  const config = load(text)
  const names = config?.publisherName
  const list = Array.isArray(names) ? names : names == null ? [] : [names]
  if (list.length === 0) return "app-update.yml names no publisher, so updates would skip the signature check"
  if (list.some((name) => typeof name !== "string" || name.trim() === "")) return "app-update.yml names an empty publisher"
  return null
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const file = process.argv[2]
  if (!file) throw new Error("usage: check-publisher-name.mjs <app-update.yml>")
  const problem = publisherNameProblem(readFileSync(file, "utf8"))
  if (problem) {
    console.error(`::error::${file}: ${problem}`)
    process.exit(1)
  }
  console.log(`${file} names its publisher, so every update's signature is checked`)
}
