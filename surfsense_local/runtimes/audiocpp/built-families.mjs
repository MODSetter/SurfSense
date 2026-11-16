// Proof that a staged server was built with every curated family, which
// --list-devices cannot give. Started on an empty model package, the server
// fails inside the family's loader; a family left out of the build is refused
// by name first. Measured on v0.8.2 builds with and without each family.
import { execFile } from "node:child_process"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { createServer } from "node:net"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { FAMILIES } from "./pins.mjs"
import { SERVER } from "./server-files.mjs"

// A GGUF v3 header with no tensors and no metadata: enough to reach the loader.
const EMPTY_GGUF = Buffer.concat([
  Buffer.from("GGUF"),
  Buffer.from([3, 0, 0, 0]),
  Buffer.alloc(16),
])

/** Whether the server's output shows `family`'s own loader reading the package. */
export function loaderRan(family, output) {
  return (
    output.includes(`model spec for family '${family}'`) &&
    !output.includes("unsupported model family")
  )
}

/** A port nothing listens on, in case a server gets as far as listening. */
function freePort() {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.once("error", reject)
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address()
      server.close(() => resolve(port))
    })
  })
}

/** Everything the server in `stage` printed while loading one empty `family` model. */
async function loadOutput(stage, work, family) {
  const config = join(work, `${family}.json`)
  writeFileSync(
    config,
    JSON.stringify({
      lazy_load: false,
      models: [{ id: "probe", family, path: join(work, "empty.gguf") }],
    })
  )
  const args = ["--config", config, "--host", "127.0.0.1", "--port", String(await freePort())]
  return new Promise((resolve) => {
    execFile(
      join(stage, SERVER),
      [...args, "--backend", "cpu", "--no-ui"],
      { cwd: stage, timeout: 120_000, windowsHide: true },
      (_error, stdout, stderr) => resolve(`${stdout}${stderr}`)
    )
  })
}

/**
 * What one family's probe shows: `built`, its loader ran; `missing`, the build
 * refused it by name; `unknown`, the server never got that far (blocked by
 * antivirus, a library missing), which says nothing about the build.
 */
export function probeVerdict(family, output) {
  if (loaderRan(family, output)) return "built"
  if (output.includes(`unsupported model family hint: ${family}`)) return "missing"
  return "unknown"
}

/** Each curated family the server in `stage` does not prove, with its verdict and output. */
export async function unprovenFamilies(stage, { families = FAMILIES, load = loadOutput } = {}) {
  const work = mkdtempSync(join(tmpdir(), "surfsense-audiocpp-families-"))
  try {
    writeFileSync(join(work, "empty.gguf"), EMPTY_GGUF)
    const unproven = []
    for (const family of families) {
      const output = await load(stage, work, family)
      const verdict = probeVerdict(family, output)
      if (verdict !== "built") unproven.push({ family, verdict, output })
    }
    return unproven
  } finally {
    rmSync(work, { recursive: true, force: true })
  }
}

/** Throw unless the server in `stage` has a loader for every curated family. */
export async function verifyBuiltFamilies(stage) {
  const [first, ...rest] = await unprovenFamilies(stage)
  if (!first) return
  const families = [first, ...rest].map(({ family }) => family).join(", ")
  throw new Error(
    first.verdict === "missing"
      ? `audiocpp_server was not built with ${families}: ${first.output}`
      : `audiocpp_server did not run to prove ${families}: ${first.output || "it printed nothing"}`
  )
}
