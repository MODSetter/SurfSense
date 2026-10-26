// Everything the sd-server runtime is made from, pinned. Upstream publishes
// rolling master builds with no checksums, so the commit pins the source and a
// locally computed sha256 pins the one archive taken as built.

export const TAG = "master-869-07a85c7"
export const COMMIT = "07a85c74cb08cda3aa176f688c5d8f522615e2b9" // pragma: allowlist secret
export const SOURCE = "https://github.com/leejet/stable-diffusion.cpp.git"

// What the build needs; the server's web page, a fifth submodule, is left out.
export const SUBMODULES = ["ggml", "thirdparty/libwebp", "thirdparty/libwebm"]

// Windows takes upstream's Vulkan archive: its server carries no AVX-512, which
// sits only in the per-CPU ggml libraries ggml picks at start.
export const WINDOWS_ARCHIVE = {
  url: `https://github.com/leejet/stable-diffusion.cpp/releases/download/${TAG}/sd-master-07a85c7-bin-win-vulkan-x64.zip`,
  sha256: "8dd5fc2c9f403de52b4b1453a8ec5bd8510919757da672ad84cd1c5fb1ff6c16", // pragma: allowlist secret
}
