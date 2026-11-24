// Fails unless a signed SurfSense.app carries build/designated-requirement.txt as
// its designated requirement, the one Squirrel.Mac holds the next update to
// (ADR 0091). Release CI runs it on the app in the dmg and in the update zip:
//   node scripts/mac-signing/designated-requirement.mjs <SurfSense.app>
import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

export const REQUIREMENT_FILE = fileURLToPath(new URL("../../build/designated-requirement.txt", import.meta.url))

/** A requirement as text, with codesign's `/* exists *\/` notes and spacing taken out. */
export function normalizedRequirement(text) {
  return text.replace(/\/\*.*?\*\//g, " ").replace(/\s+/g, " ").trim()
}

const DESIGNATED = "designated => "

/** The explicit designated requirement in `codesign -d -r-` output; an implicit one prints as `# designated`. */
export function designatedRequirement(output) {
  const line = output.split(/\r?\n/).find((entry) => entry.startsWith(DESIGNATED))
  return line === undefined ? null : normalizedRequirement(line.slice(DESIGNATED.length))
}

export function requirementProblem(output, expected) {
  const shipped = designatedRequirement(output)
  if (shipped === null) return "the app carries no explicit designated requirement"
  const wanted = designatedRequirement(expected)
  return shipped === wanted ? null : `the app's designated requirement is ${shipped}, not ${wanted}`
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const app = process.argv[2]
  if (!app) throw new Error("usage: designated-requirement.mjs <SurfSense.app>")
  // codesign writes "Executable=..." to stderr and the requirements to stdout.
  const output = execFileSync("codesign", ["-d", "-r-", app], { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] })
  const problem = requirementProblem(output, readFileSync(REQUIREMENT_FILE, "utf8"))
  if (problem) {
    console.error(`::error::${app}: ${problem}`)
    process.exit(1)
  }
  console.log(`${app}: ${designatedRequirement(output)}`)
}
