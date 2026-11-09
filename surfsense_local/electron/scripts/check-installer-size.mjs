// Fails when one of this OS's installers is missing or over its budget, MiB per artifact
// name in installer-size-budgets.json.
//   node scripts/check-installer-size.mjs [release folder] [budgets file]
import { existsSync, readFileSync, statSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

const MiB = 1024 * 1024
const RELEASE = fileURLToPath(new URL("../release", import.meta.url))
const BUDGETS = fileURLToPath(new URL("./installer-size-budgets.json", import.meta.url))

/** @returns {Record<string, { platform: NodeJS.Platform, maxMiB: number }>} */
export function readBudgets(file = BUDGETS) {
  return JSON.parse(readFileSync(file, "utf8"))
}

/** Each of `platform`'s installers in `releaseDir` against its budget; `failed` when one is over or missing. */
export function checkInstallerSizes({ releaseDir, budgets, platform = process.platform }) {
  const mine = Object.entries(budgets).filter(([, budget]) => budget.platform === platform)
  if (!mine.length) throw new Error(`no installer budgets for ${platform}`)
  const rows = mine.map(([name, { maxMiB }]) => {
    const path = join(releaseDir, name)
    if (!existsSync(path)) return { name, sizeMiB: null, maxMiB, status: "missing" }
    const sizeMiB = statSync(path).size / MiB
    return { name, sizeMiB, maxMiB, status: sizeMiB > maxMiB ? "over" : "ok" }
  })
  return { rows, failed: rows.some((row) => row.status !== "ok") }
}

const LABEL = { ok: "ok", over: "OVER BUDGET", missing: "NOT BUILT" }

function describe({ name, sizeMiB, maxMiB, status }) {
  const size = sizeMiB === null ? "-" : `${sizeMiB.toFixed(1)} MiB`
  return `${name.padEnd(24)} ${size.padStart(12)}  of ${maxMiB.toFixed(1)} MiB  ${LABEL[status]}`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [releaseDir = RELEASE, budgetsFile = BUDGETS] = process.argv.slice(2)
  const { rows, failed } = checkInstallerSizes({ releaseDir, budgets: readBudgets(budgetsFile) })
  for (const row of rows) console.log(describe(row))
  if (failed) {
    console.error(`an installer is over budget or was not built; budgets: ${budgetsFile}`)
    process.exitCode = 1
  }
}
