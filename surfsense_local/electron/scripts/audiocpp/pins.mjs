// Everything the audio.cpp runtime is made from, pinned. A tag can move, so
// the commit is what pins the source; every download is pinned by sha256.

export const TAG = "v0.8.2"
export const COMMIT = "4d88768fbcae4e6eb3352c6ab1422dabb7d90b58" // pragma: allowlist secret
export const SOURCE = "https://github.com/0xShug0/audio.cpp.git"

// The families the app curates: the only ones built, and their specs ship.
export const FAMILIES = ["kokoro_tts", "supertonic", "kitten_tts"]

// macOS takes upstream's archive, which meets the app's floor there.
export const MAC_ARCHIVE = {
  url: `https://github.com/0xShug0/audio.cpp/releases/download/${TAG}/audio-${TAG}-bin-macos-arm64-metal.tar.gz`,
  sha256: "d33db13695fbf3ba73ea85a8b59575b98a66f7b6ff89bbb59599c75b4689f9a5", // pragma: allowlist secret
}

// eSpeak-ng 1.52.0 as the espeakng-loader wheel packages it, GPL-3.0-or-later.
// Kokoro and Kitten phonemise through it, and audio.cpp does not ship it.
const WHEELS = "https://files.pythonhosted.org/packages"
export const ESPEAK = {
  darwin: {
    url: `${WHEELS}/a8/26/258c0cd43b9bc1043301c5f61767d6a6c3b679df82790c9cb43a3277b865/espeakng_loader-0.2.4-py3-none-macosx_11_0_arm64.whl`,
    sha256: "d27cdca31112226e7299d8562e889d3e38a1e48055c9ee381b45d669072ee59f", // pragma: allowlist secret
    library: "libespeak-ng.dylib",
  },
  linux: {
    url: `${WHEELS}/de/1e/25ec5ab07528c0fbb215a61800a38eca05c8a99445515a02d7fa5debcb32/espeakng_loader-0.2.4-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`,
    sha256: "08721baf27d13d461f6be6eed9a65277e70d68234ff484fd8b9897b222cdcb6d", // pragma: allowlist secret
    library: "libespeak-ng.so",
  },
  win32: {
    url: `${WHEELS}/9d/ed/a3d872fbad4f3a3f3db0e8c31768ab14e77cd77306de16b8b20b1e1df7ea/espeakng_loader-0.2.4-py3-none-win_amd64.whl`,
    sha256: "41f1e08ac9deda2efd1ea9de0b81dab9f5ae3c4b24284f76533d0a7b1dd7abd7", // pragma: allowlist secret
    library: "espeak-ng.dll",
  },
}

// The wheel carries no licence text, and the GPL requires it beside the library.
export const ESPEAK_LICENCE = {
  url: "https://raw.githubusercontent.com/espeak-ng/espeak-ng/1.52.0/COPYING",
  sha256: "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903", // pragma: allowlist secret
}
