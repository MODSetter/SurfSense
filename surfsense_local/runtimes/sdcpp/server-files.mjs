// The server, the libraries it loads from beside itself, and the licences:
// what the sidecar runs, copied into the stage. sd-cli is left behind.
import { chmodSync, copyFileSync, existsSync, readdirSync, readlinkSync, symlinkSync } from "node:fs"
import { join } from "node:path"

export const SERVER = process.platform === "win32" ? "sd-server.exe" : "sd-server"
const LIBRARY = /\.(dylib|so)(\.\d+)*$|\.dll$/i
const LICENCES = ["stable-diffusion.cpp.txt", "ggml.txt"]

/** `binaries` is the flat folder a build or an archive puts everything in. */
export function copyServerFiles(binaries, stage) {
  for (const name of [SERVER, ...LICENCES]) {
    if (!existsSync(join(binaries, name))) throw new Error(`no ${name} in ${binaries}`)
  }
  for (const entry of readdirSync(binaries, { withFileTypes: true })) {
    const wanted = entry.name === SERVER || LICENCES.includes(entry.name) || LIBRARY.test(entry.name)
    if (!wanted) continue
    const from = join(binaries, entry.name)
    const to = join(stage, entry.name)
    // Links stay links: the loader resolves the versioned names they carry.
    if (entry.isSymbolicLink()) {
      symlinkSync(readlinkSync(from), to)
      continue
    }
    copyFileSync(from, to)
    if (process.platform !== "win32" && !entry.name.endsWith(".txt")) chmodSync(to, 0o755)
  }
}
