// The native programs the installer carries, and the licence files their
// stage scripts already leave beside them. Folders are relative to electron/.
import { readFileSync } from "node:fs"

import { DICTIONARIES_FOR, KEPT_DICTIONARIES } from "../../../runtimes/audiocpp/espeak/dictionaries.mjs"
import { ESPEAK_VERSION, TAG as AUDIOCPP_TAG } from "../../../runtimes/audiocpp/pins.mjs"
import { BUILD as LLAMACPP_BUILD } from "../../../runtimes/fetch-llamacpp.mjs"
import { RIPGREP_VERSION, VERSION as OPENCODE_VERSION } from "../../../runtimes/opencode/pins.mjs"
import { TAG as SDCPP_TAG } from "../../../runtimes/sdcpp/pins.mjs"

function electronVersion() {
  try {
    const pkg = new URL("../../node_modules/electron/package.json", import.meta.url)
    return JSON.parse(readFileSync(pkg, "utf8")).version
  } catch {
    return "unknown"
  }
}

export const NATIVE_COMPONENTS = [
  { name: "Electron", version: electronVersion(), license: "MIT", folder: "node_modules/electron/dist", files: ["LICENSE"],
    note: "Chromium's notices ship with Electron as LICENSES.chromium.html beside the app." },
  // The llama.cpp licence covers the ggml it vendors: same authors, same text.
  { name: "llama.cpp", version: LLAMACPP_BUILD, license: "MIT", folder: "llamacpp", files: ["LICENSE"] },
  // fetch-llamacpp.mjs stages it beside the libomp.dll only Windows' archive carries.
  { name: "LLVM OpenMP (in llama.cpp)", version: LLAMACPP_BUILD, license: "Apache-2.0 WITH LLVM-exception", folder: "llamacpp",
    files: ["LICENSE-LLVM-OpenMP"], platforms: ["win32"] },
  { name: "stable-diffusion.cpp", version: SDCPP_TAG, license: "MIT", folder: "sdcpp", files: ["stable-diffusion.cpp.txt"] },
  { name: "ggml (in stable-diffusion.cpp)", version: SDCPP_TAG, license: "MIT", folder: "sdcpp", files: ["ggml.txt"] },
  { name: "audio.cpp", version: AUDIOCPP_TAG, license: "Apache-2.0", folder: "audiocpp", files: ["LICENSE"] },
  // The GPL asks a modified copy to say so and give a date; the trimmed data is one.
  { name: "eSpeak NG", version: ESPEAK_VERSION, license: "GPL-3.0-or-later", folder: "audiocpp", files: ["espeak/COPYING"],
    note: `SurfSense modified this copy on ${DICTIONARIES_FOR.on}, trimming eSpeak NG's data to the dictionaries ` +
      `its voices can use: ${KEPT_DICTIONARIES.join(", ")}. The complete source, every dictionary included, is at ` +
      `https://github.com/espeak-ng/espeak-ng/tree/${ESPEAK_VERSION}.` },
  { name: "opencode", version: OPENCODE_VERSION, license: "MIT", folder: "opencode", files: ["LICENSE"] },
  { name: "ripgrep", version: RIPGREP_VERSION, license: "Unlicense OR MIT", folder: "opencode",
    files: ["ripgrep/COPYING", "ripgrep/LICENSE-MIT", "ripgrep/UNLICENSE"] },
]
