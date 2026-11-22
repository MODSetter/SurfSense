// llama.cpp's licence files, staged beside the server under their own names.
//
// The macOS and Linux archives carry llama.cpp's LICENSE. The Windows ones do
// not: their one licence file is LLVM OpenMP's, LICENSE-LLVM-OpenMP, for the
// libomp.dll beside llama-server. So llama.cpp's own comes from the copy kept
// here, taken at the pinned build, and an archive that carries one must match
// it, which keeps the copy current when the build moves.
import { copyFileSync, readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

export const PINNED_LICENSE = fileURLToPath(new URL("llama.cpp-LICENSE", import.meta.url))

const OWN = "LICENSE"
// A bundled library's licence, as LICENSE-LLVM-OpenMP is.
const BUNDLED = /^LICENSE-.+/i

const text = (path) => readFileSync(path, "utf8").replace(/\r\n/g, "\n")

/** Copy the licence files in `source` into `stage`, and return their names. */
export function stageLicences(source, stage, pinned = PINNED_LICENSE) {
  const names = readdirSync(source, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name)
  const bundled = names.filter((name) => BUNDLED.test(name))
  for (const name of bundled) copyFileSync(join(source, name), join(stage, name))

  if (!names.includes(OWN)) {
    copyFileSync(pinned, join(stage, OWN))
  } else if (text(join(source, OWN)) === text(pinned)) {
    copyFileSync(join(source, OWN), join(stage, OWN))
  } else {
    throw new Error(`the archive's ${OWN} differs from ${pinned}: replace that copy with the archive's`)
  }
  return [OWN, ...bundled].sort()
}
