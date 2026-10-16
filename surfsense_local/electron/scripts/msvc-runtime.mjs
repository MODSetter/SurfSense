// Visual Studio's C++ toolchain on Windows: whether it is installed, and the
// runtime DLLs it redistributes, which ship beside the server so a clean
// Windows runs it without a separately installed redistributable.
import { execFileSync } from "node:child_process"
import { copyFileSync, existsSync, readdirSync } from "node:fs"
import { join } from "node:path"

const VSWHERE = join(
  process.env["ProgramFiles(x86)"] ?? "C:\\Program Files (x86)",
  "Microsoft Visual Studio",
  "Installer",
  "vswhere.exe"
)

/** The newest Visual Studio with the x64 C++ tools, or null. */
export function visualStudio() {
  if (!existsSync(VSWHERE)) return null
  const path = execFileSync(
    VSWHERE,
    [
      "-latest",
      "-products",
      "*",
      "-requires",
      "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
      "-property",
      "installationPath",
    ],
    { encoding: "utf8" }
  ).trim()
  return path || null
}

/** CMake's generator for that Visual Studio, such as "Visual Studio 17 2022", or null. */
export function visualStudioGenerator() {
  if (!existsSync(VSWHERE)) return null
  const [found] = JSON.parse(
    execFileSync(
      VSWHERE,
      [
        "-latest",
        "-products",
        "*",
        "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
        "-format",
        "json",
        "-utf8",
      ],
      { encoding: "utf8" }
    )
  )
  return found ? generatorName(found.installationVersion, found.catalog?.productLineVersion) : null
}

// Visual Studio 2026's vswhere gives "18" as its product line, not the year.
const YEAR_BY_MAJOR = { 15: "2017", 16: "2019", 17: "2022", 18: "2026" }

/** CMake names a Visual Studio by its major version and its year, or null when the year is unknown. */
export function generatorName(installationVersion, productLineVersion) {
  const major = installationVersion.split(".")[0]
  const year = /^\d{4}$/.test(productLineVersion ?? "") ? productLineVersion : YEAR_BY_MAJOR[major]
  return year ? `Visual Studio ${major} ${year}` : null
}

const byVersion = (a, b) => {
  const [x, y] = [a, b].map((v) => v.split(".").map(Number))
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) - (y[i] ?? 0)
  }
  return 0
}

/** `openmp` adds vcomp140.dll, for a build whose ggml was compiled with OpenMP. */
export function copyMsvcRuntime(stage, { openmp = false } = {}) {
  const vs = visualStudio()
  const redist = vs && join(vs, "VC", "Redist", "MSVC")
  if (!redist || !existsSync(redist)) throw new Error("no MSVC redistributable to ship")
  const versions = readdirSync(redist).filter((name) => /^\d+(\.\d+)+$/.test(name))
  for (const version of versions.sort(byVersion).reverse()) {
    const x64 = join(redist, version, "x64")
    if (!existsSync(x64)) continue
    const crt = readdirSync(x64).find((name) => /^Microsoft\.VC\d+\.CRT$/.test(name))
    if (!crt) continue
    for (const dll of readdirSync(join(x64, crt))) {
      if (/^(vcruntime140|msvcp140).*\.dll$/i.test(dll)) {
        copyFileSync(join(x64, crt, dll), join(stage, dll))
      }
    }
    if (openmp) {
      const omp = readdirSync(x64).find((name) => /^Microsoft\.VC\d+\.OpenMP$/.test(name))
      if (!omp) throw new Error(`no OpenMP runtime beside ${crt}`)
      copyFileSync(join(x64, omp, "vcomp140.dll"), join(stage, "vcomp140.dll"))
    }
    return
  }
  throw new Error(`no x64 CRT under ${redist}`)
}
