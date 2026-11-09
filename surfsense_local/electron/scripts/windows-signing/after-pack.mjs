// electron-builder's afterPack hook. On a signed Windows build it signs every
// native library the app carries that has no valid signature: electron-builder
// signs only .exe files, and Smart App Control refuses an unsigned .dll or .pyd
// it has no reputation for, as it refused chonkie_core's in 2.2.5 (#2366). It
// runs before electron-builder signs SurfSense.exe and makes the installer, so a
// tag's build never uploads one that carries an unsigned library.
import { signWithAzure } from "./azure-sign.mjs"
import { nativeLibraries } from "./native-libraries.mjs"
import { signatureStatuses } from "./signature-status.mjs"

/** @param {import("electron-builder").AfterPackContext} context */
export default async function afterPack(context, { statusesOf = signatureStatuses, sign = signWithAzure } = {}) {
  if (context.electronPlatformName !== "win32") return
  // Set only on a production tag's build, as for the .exe files.
  const azure = context.packager.platformSpecificBuildOptions.azureSignOptions
  if (!azure) {
    console.log("unsigned build: native libraries left as they are")
    return
  }
  const libraries = nativeLibraries(context.appOutDir)
  // A vendor's valid signature stays, as Python's and Microsoft's do.
  const unsigned = withoutValidSignature(libraries, statusesOf)
  if (unsigned.length > 0) sign(unsigned, azure, context.outDir)
  const left = withoutValidSignature(libraries, statusesOf)
  if (left.length > 0) {
    throw new Error(`${left.length} native libraries are still unsigned:\n${left.join("\n")}`)
  }
  console.log(`signed ${unsigned.length} of ${libraries.length} native libraries; the rest were signed already`)
}

function withoutValidSignature(files, statusesOf) {
  const statuses = statusesOf(files)
  return files.filter((_, index) => statuses[index] !== "Valid")
}
