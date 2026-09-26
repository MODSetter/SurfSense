import { describe, expect, it } from "vitest"

import { buildSize } from "./build-size"
import type { LocalBuild } from "./chat/api"

const build = (fields: Partial<LocalBuild>) =>
  ({
    footprint_bytes: 5_170_000_000,
    installed_as: null,
    ...fields,
  }) as LocalBuild

describe("a build's size on its row", () => {
  it("is what Download fetches, less files another model brought", () => {
    // Z-Image after FLUX.2 klein: the text encoder is already on disk.
    expect(buildSize(build({ download_bytes: 4_020_000_000 }))).toBe(
      4_020_000_000
    )
  })

  it("is the whole footprint where nothing is shared", () => {
    expect(buildSize(build({ download_bytes: null }))).toBe(5_170_000_000)
    expect(buildSize(build({}))).toBe(5_170_000_000)
  })

  it("is what it takes on disk once it is there", () => {
    expect(
      buildSize(build({ installed_as: "klein-Q4_0", download_bytes: 0 }))
    ).toBe(5_170_000_000)
  })
})
