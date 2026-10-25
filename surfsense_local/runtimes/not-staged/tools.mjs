// What a stage can lack, and the packages that provide it per package manager.
// Vulkan's are llama.cpp's (docs/build.md): its loader does not always pull in
// SPIR-V's headers. GCC 13 is each distribution's default g++ only from
// Ubuntu 24.04 and Fedora 39.

export const CMAKE = {
  name: "CMake",
  packages: {
    apt: ["cmake"],
    dnf: ["cmake"],
    pacman: ["cmake"],
    brew: ["cmake"],
    winget: ["Kitware.CMake"],
  },
}

export const GCC_13 = {
  name: "GCC 13 or newer",
  packages: { apt: ["g++"], dnf: ["gcc-c++"], pacman: ["gcc"] },
}

export const CXX_COMPILER = {
  name: "a C++ compiler",
  packages: { apt: ["g++"], dnf: ["gcc-c++"], pacman: ["gcc"] },
}

export const VULKAN_SDK = {
  name: "the Vulkan SDK (glslc and headers)",
  packages: {
    apt: ["glslc", "libvulkan-dev", "spirv-headers"],
    dnf: ["glslc", "vulkan-loader-devel", "spirv-headers-devel"],
    pacman: ["shaderc", "vulkan-icd-loader", "vulkan-headers", "spirv-headers"],
  },
}

export const XCODE_TOOLS = {
  name: "Xcode's command line tools",
  command: "xcode-select --install",
}

export const VISUAL_STUDIO = {
  name: "Visual Studio 2022 or newer with the C++ tools",
  packages: {
    winget: [
      'Microsoft.VisualStudio.2022.BuildTools --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"',
    ],
  },
}
