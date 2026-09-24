// How audio.cpp is configured for Windows and Linux: a CPU-only server that
// runs on any x64 CPU and, on Linux, on glibc 2.34 without a newer C++ runtime.
import { FAMILIES, TAG } from "./pins.mjs"

const PORTABLE_CPU_ONLY = [
  // The GPU is the chat model's, so the server runs with --backend cpu.
  "-DENGINE_ENABLE_CUDA=OFF",
  "-DENGINE_ENABLE_HIP=OFF",
  "-DENGINE_ENABLE_VULKAN=OFF",
  "-DENGINE_ENABLE_METAL=OFF",
  // One ggml library per micro-architecture, chosen at start.
  "-DENGINE_ENABLE_NATIVE_CPU=OFF",
  "-DENGINE_ENABLE_CPU_ALL_VARIANTS=ON",
  // ggml's own thread pool, so no libgomp or vcomp ships.
  "-DENGINE_ENABLE_OPENMP=OFF",
  "-DGGML_OPENMP=OFF",
  "-DAUDIOCPP_DEPLOYMENT_BUILD=ON",
  "-DAUDIOCPP_MODEL_SET=custom",
  `-DAUDIOCPP_MODELS=${FAMILIES.join(",")}`,
  `-DAUDIOCPP_VERSION=${TAG.replace(/^v/, "")}`,
]

// libstdc++ goes into every file, ggml's backend modules included, because
// audio.cpp needs GCC 13 and older systems carry an older libstdc++. libgcc
// stays dynamic: GCC 13's static unwinder on 22.04 calls glibc 2.35.
const STATIC_LIBSTDCXX = ["EXE", "SHARED", "MODULE"].map(
  (kind) => `-DCMAKE_${kind}_LINKER_FLAGS=-static-libstdc++`
)

/** The arguments after `cmake -S <source> -B <build>`. */
export function configureArgs(platform) {
  if (platform === "win32") return ["-A", "x64", ...PORTABLE_CPU_ONLY]
  return ["-DCMAKE_BUILD_TYPE=Release", ...PORTABLE_CPU_ONLY, ...STATIC_LIBSTDCXX]
}
