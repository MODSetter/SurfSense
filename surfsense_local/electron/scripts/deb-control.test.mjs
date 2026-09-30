import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

/** The `deb:` section of electron-builder.yml, one entry per list line. */
function debSection() {
  const yml = readFileSync(new URL("../electron-builder.yml", import.meta.url), "utf8")
  const block = yml.match(/^deb:\n((?:[ \t]+.*\n|\n)*)/m)?.[1] ?? ""
  const list = (key) =>
    block
      .match(new RegExp(`^  ${key}:\\n((?:    - .*\\n)*)`, "m"))?.[1]
      .split("\n")
      .filter(Boolean)
      .map((line) => line.replace(/^\s*-\s*/, "").trim()) ?? null
  return { recommends: list("recommends"), depends: list("depends") }
}

test("the deb recommends the Vulkan loader llama.cpp's GPU backend opens", () => {
  // Without it ggml skips the backend and every model runs on the CPU.
  assert.ok(debSection().recommends?.includes("libvulkan1"))
})

test("the deb keeps electron-builder's own recommendation", () => {
  // Setting `recommends` replaces the default list rather than adding to it.
  assert.ok(debSection().recommends?.includes("libappindicator3-1"))
})

test("the deb leaves electron-builder's depends list as it is", () => {
  // Setting `depends` would replace the GTK, NSS and X libraries Electron needs.
  assert.equal(debSection().depends, null)
})
