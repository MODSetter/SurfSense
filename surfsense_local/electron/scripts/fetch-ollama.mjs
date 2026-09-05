// Stage the Ollama server into electron/ollama so electron-builder can ship it
// as a sidecar (see electron-builder.yml extraResources, sidecars/ollama.ts).
// Downloads the standalone archive for the host OS and extracts it, native
// layout preserved (bin/ollama + lib/ollama, or ollama.exe + lib on Windows).
// Idempotent: a present binary is left alone. Run per-OS, on the same machine
// that packages the app (the runtime can't be cross-fetched).
import { execFileSync } from "node:child_process"
import { existsSync, mkdirSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

const OUT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "ollama")
const BASE = "https://ollama.com/download"

// Full GPU-capable archives, one per host. arm64 desktop isn't a build target yet.
const TARGETS = {
  "linux-x64": { url: `${BASE}/ollama-linux-amd64.tgz`, kind: "tgz" },
  "darwin-x64": { url: `${BASE}/ollama-darwin.tgz`, kind: "tgz" },
  "darwin-arm64": { url: `${BASE}/ollama-darwin.tgz`, kind: "tgz" },
  "win32-x64": { url: `${BASE}/ollama-windows-amd64.zip`, kind: "zip" },
}

const binary = process.platform === "win32" ? "ollama.exe" : "ollama"
const staged = [join(OUT, "bin", binary), join(OUT, binary)]
if (staged.some(existsSync)) {
  console.log(`ollama already staged in ${OUT}`)
  process.exit(0)
}

const key = `${process.platform}-${process.arch}`
const target = TARGETS[key]
if (!target) {
  console.error(`no bundled ollama for ${key}`)
  process.exit(1)
}

rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })

const archive = join(tmpdir(), `ollama.${target.kind}`)
console.log(`downloading ${target.url}`)
execFileSync("curl", ["-fSL", "--retry", "3", target.url, "-o", archive], { stdio: "inherit" })

console.log(`extracting into ${OUT}`)
// bsdtar (macOS/Windows) reads zip too; -z handles the gzip tarballs on posix.
execFileSync("tar", [target.kind === "tgz" ? "-xzf" : "-xf", archive, "-C", OUT], {
  stdio: "inherit",
})
rmSync(archive, { force: true })

if (!staged.some(existsSync)) {
  console.error(`extraction did not yield ${binary} under ${OUT}`)
  process.exit(1)
}
console.log("ollama staged")
