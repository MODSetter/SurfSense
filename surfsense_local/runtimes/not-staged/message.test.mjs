import assert from "node:assert/strict"
import test from "node:test"

import { notStaged } from "./message.mjs"
import { CMAKE, CXX_COMPILER, GCC_13, VISUAL_STUDIO, VULKAN_SDK, XCODE_TOOLS } from "./tools.mjs"

const HOW = "on Linux it is compiled from source"

test("says nothing when nothing is missing", () => {
  assert.equal(notStaged("audio.cpp", HOW, [], "apt"), null)
})

test("names the one tool missing and what to do", () => {
  assert.equal(
    notStaged("audio.cpp", HOW, [CMAKE], null),
    "audio.cpp is not staged: on Linux it is compiled from source, and this machine lacks CMake. Install what is missing and run the build again."
  )
})

test("names every missing tool at once, so one install fixes the build", () => {
  assert.equal(
    notStaged("audio.cpp", HOW, [CMAKE, GCC_13], null),
    "audio.cpp is not staged: on Linux it is compiled from source, and this machine lacks CMake and GCC 13 or newer. Install what is missing and run the build again."
  )
  assert.equal(
    notStaged("sd-server", HOW, [CMAKE, CXX_COMPILER, VULKAN_SDK], null),
    "sd-server is not staged: on Linux it is compiled from source, and this machine lacks CMake, a C++ compiler and the Vulkan SDK (glslc and headers). Install what is missing and run the build again."
  )
})

test("shows the one command that installs everything missing", () => {
  assert.equal(
    notStaged("audio.cpp", HOW, [CMAKE, GCC_13], "apt"),
    `audio.cpp is not staged: on Linux it is compiled from source, and this machine lacks CMake and GCC 13 or newer. Install what is missing, then run the build again:

  sudo apt install cmake g++`
  )
})

test("on Windows, one winget call per package", () => {
  assert.equal(
    notStaged("audio.cpp", "on Windows it is compiled from source", [CMAKE, VISUAL_STUDIO], "winget"),
    `audio.cpp is not staged: on Windows it is compiled from source, and this machine lacks CMake and Visual Studio 2022 or newer with the C++ tools. Install what is missing, then run the build again:

  winget install Kitware.CMake
  winget install Microsoft.VisualStudio.2022.BuildTools --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`
  )
})

test("on macOS, Xcode's tools come from xcode-select, not Homebrew", () => {
  assert.equal(
    notStaged("sd-server", "on macOS it is compiled from source", [CMAKE, XCODE_TOOLS], "brew"),
    `sd-server is not staged: on macOS it is compiled from source, and this machine lacks CMake and Xcode's command line tools. Install what is missing, then run the build again:

  xcode-select --install
  brew install cmake`
  )
})

test("a tool no package fixes is named but left out of the command", () => {
  // The distribution's g++ is already installed, and too old.
  const oldGcc = { name: "GCC 13 or newer (g++ is 11.4.0)" }
  assert.equal(
    notStaged("audio.cpp", HOW, [CMAKE, oldGcc], "apt"),
    `audio.cpp is not staged: on Linux it is compiled from source, and this machine lacks CMake and GCC 13 or newer (g++ is 11.4.0). Install what is missing, then run the build again:

  sudo apt install cmake`
  )
})
