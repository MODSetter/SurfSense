// How sd.cpp is configured where it is compiled: Linux, for glibc 2.34, and
// macOS, for 13.3. Upstream's archives need glibc 2.38 and macOS 26.0.

const OUTPUTS = [
  "-DCMAKE_BUILD_TYPE=Release",
  "-DSD_BUILD_SHARED_LIBS=ON",
  "-DSD_WEBP=ON",
  "-DSD_WEBM=ON",
  "-DSD_SERVER_BUILD_FRONTEND=OFF",
  "-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON",
]

const LINUX = [
  "-DSD_VULKAN=ON",
  // ggml as its own libraries, so each backend is a module picked at start:
  // one per CPU micro-architecture, and Vulkan.
  "-DSD_BUILD_SHARED_GGML_LIB=ON",
  "-DGGML_NATIVE=OFF",
  "-DGGML_BACKEND_DL=ON",
  "-DGGML_CPU_ALL_VARIANTS=ON",
  // ggml's own thread pool, so no libgomp ships.
  "-DGGML_OPENMP=OFF",
  "-DCMAKE_INSTALL_RPATH=$ORIGIN",
  // Into every file, ggml's modules included. libgcc stays dynamic: GCC's
  // static unwinder on 22.04 calls glibc 2.35.
  ...["EXE", "SHARED", "MODULE"].map((kind) => `-DCMAKE_${kind}_LINKER_FLAGS=-static-libstdc++`),
]

// llama.cpp's macOS release flags, which set the same floor.
const DARWIN = [
  "-DSD_METAL=ON",
  "-DGGML_METAL_EMBED_LIBRARY=ON",
  "-DCMAKE_OSX_ARCHITECTURES=arm64",
  "-DCMAKE_OSX_DEPLOYMENT_TARGET=13.3",
  "-DCMAKE_INSTALL_RPATH=@loader_path",
]

/** The arguments after `cmake -S <source> -B <build>`. */
export function configureArgs(platform) {
  if (platform === "linux") return [...OUTPUTS, ...LINUX]
  if (platform === "darwin") return [...OUTPUTS, ...DARWIN]
  throw new Error(`sd.cpp is not compiled on ${platform}`)
}
