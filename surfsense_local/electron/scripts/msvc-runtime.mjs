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
