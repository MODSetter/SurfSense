// Stage stable-diffusion.cpp's sd-server into electron/sdcpp so electron-builder
// can ship it as a sidecar (see electron-builder.yml extraResources,
// sidecars/sdcpp.ts). It serves POST /v1/images/generations, which is the route
// the image provider already speaks, so it needs no client of its own.
//
// Only the Vulkan and Metal builds are staged. The CUDA and ROCm archives are
// 182-537 MB and Vulkan already reaches NVIDIA, AMD, and Intel through the host
// driver -- the same trade the bundled llama.cpp build makes.
//
// Upstream publishes rolling master builds with no semver and no checksums, so
// the tag and a locally computed SHA-256 are both pinned here. Bump deliberately.
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import {
  chmodSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

const TAG = "master-869-07a85c7"
const BASE = `https://github.com/leejet/stable-diffusion.cpp/releases/download/${TAG}`
const OUT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "sdcpp")

// No prebuilt binary exists for Intel macOS or arm64 Linux. Those hosts stage an
// empty directory: packaging still succeeds and sdcppSpec finds no binary, so the
// app runs without local image generation rather than failing to build.
const TARGETS = {
  "win32-x64": {
    asset: "sd-master-07a85c7-bin-win-vulkan-x64.zip",
    sha256: "8dd5fc2c9f403de52b4b1453a8ec5bd8510919757da672ad84cd1c5fb1ff6c16",
  },
  "darwin-arm64": {
    asset: "sd-master-07a85c7-bin-Darwin-macOS-26.6.2-arm64.zip",
    sha256: "0fc228abbfbf3fffd9c62c498136a9448e8e8cb5f5f29091748731cf587a4859",
  },
  "linux-x64": {
    asset: "sd-master-07a85c7-bin-Linux-Ubuntu-24.04-x86_64-vulkan.zip",
    sha256: "550b4b3bb0b0e98c13ba7569e39e2ec90b9f8fa9e3dd641689e835278000555f",
  },
}

// Under bash on Windows, PATH resolves to Git's GNU tar, which reads "C:\..." as a host and can't open zip.
const TAR =
  process.platform === "win32" ? join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe") : "tar"

const binary = process.platform === "win32" ? "sd-server.exe" : "sd-server"
const key = `${process.platform}-${process.arch}`
const target = TARGETS[key]

if (existsSync(join(OUT, binary))) {
  console.log(`sd-server already staged in ${OUT}`)
  process.exit(0)
}

mkdirSync(OUT, { recursive: true })
if (!target) {
  console.warn(`no sd-server build for ${key}; local image generation is unavailable`)
  process.exit(0)
}

const archive = join(tmpdir(), target.asset)
const url = `${BASE}/${target.asset}`
console.log(`downloading ${url}`)
execFileSync("curl", ["-fSL", "--retry", "3", url, "-o", archive], { stdio: "inherit" })

const actual = createHash("sha256").update(readFileSync(archive)).digest("hex")
if (actual !== target.sha256) {
  rmSync(archive, { force: true })
  throw new Error(`SHA-256 mismatch for ${target.asset}: expected ${target.sha256}, got ${actual}`)
}

// The archive is flat: sd-server plus the ggml backends it loads by path.
if (process.platform === "linux") {
  execFileSync("unzip", ["-o", archive, "-d", OUT], { stdio: "inherit" })
} else {
  execFileSync(TAR, ["-xf", archive, "-C", OUT], { stdio: "inherit" })
}
rmSync(archive, { force: true })

if (!existsSync(join(OUT, binary))) {
  throw new Error(`${target.asset} did not contain ${binary}`)
}
// The zips do carry the mode bit today; set it anyway rather than depend on it,
// the way fetch-llmfit.mjs does.
if (process.platform !== "win32") chmodSync(join(OUT, binary), 0o755)
// MIT, and the archive does not carry it.
writeFileSync(
  join(OUT, "LICENSE-NOTE.txt"),
  `stable-diffusion.cpp (${TAG}) is MIT licensed.\n` +
    "Source and licence: https://github.com/leejet/stable-diffusion.cpp\n",
)
console.log(`sd-server staged in ${OUT} (${target.asset})`)
