// Downloads checked against their pinned sha256, and the archives they unpack.
import { execFileSync } from "node:child_process"
import { createHash } from "node:crypto"
import { writeFileSync } from "node:fs"
import { join } from "node:path"

// Under bash on Windows, PATH resolves to Git's GNU tar, which can't open a zip.
const TAR =
  process.platform === "win32"
    ? join(process.env.SystemRoot ?? "C:\\Windows", "System32", "tar.exe")
    : "tar"

export async function download({ url, sha256 }, destination) {
  const response = await fetch(url, { redirect: "follow" })
  if (!response.ok) throw new Error(`download failed (${response.status}): ${url}`)
  const bytes = Buffer.from(await response.arrayBuffer())
  const actual = createHash("sha256").update(bytes).digest("hex")
  if (actual !== sha256) {
    throw new Error(`SHA-256 mismatch for ${url}: expected ${sha256}, got ${actual}`)
  }
  writeFileSync(destination, bytes)
}

/** A wheel is a zip too. GNU tar can't read one; Windows' and macOS' bsdtar can. */
export function unpack(archive, into) {
  if (process.platform === "linux" && /\.(zip|whl)$/.test(archive)) {
    execFileSync("unzip", ["-q", "-o", archive, "-d", into], { stdio: "inherit" })
  } else {
    execFileSync(TAR, ["-xf", archive, "-C", into], { stdio: "inherit" })
  }
}
