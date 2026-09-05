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
// Pinned to a release: ollama.com/download stopped serving stable archive URLs,
// and a pinned runtime keeps the packaged build reproducible. Bump deliberately.
const VERSION = "v0.33.3"
const BASE = `https://github.com/ollama/ollama/releases/download/${VERSION}`

// Full GPU-capable archives, one per host. Linux ships zstd tarballs now; macOS
// stays gzip, Windows zip.
const TARGETS = {
  "linux-x64": { url: `${BASE}/ollama-linux-amd64.tar.zst`, kind: "zst" },
  "linux-arm64": { url: `${BASE}/ollama-linux-arm64.tar.zst`, kind: "zst" },
  "darwin-x64": { url: `${BASE}/ollama-darwin.tgz`, kind: "tgz" },
  "darwin-arm64": { url: `${BASE}/ollama-darwin.tgz`, kind: "tgz" },
  "win32-x64": { url: `${BASE}/ollama-windows-amd64.zip`, kind: "zip" },
}

// tar flags per archive kind (bsdtar reads zip on macOS/Windows).
const TAR_FLAGS = {
  tgz: ["-xzf"],
  zst: ["--zstd", "-xf"],
  zip: ["-xf"],
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
execFileSync("tar", [...TAR_FLAGS[target.kind], archive, "-C", OUT], {
  stdio: "inherit",
})
rmSync(archive, { force: true })

if (!staged.some(existsSync)) {
  console.error(`extraction did not yield ${binary} under ${OUT}`)
  process.exit(1)
}
console.log("ollama staged")
