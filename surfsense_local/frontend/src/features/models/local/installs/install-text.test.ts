import { describe, expect, it } from "vitest"

import { installMessage } from "./install-text"

describe("what an install event says", () => {
  it("shows the interface's own line for a code it knows", () => {
    // The backend's sentence is English in every language; the code is what
    // the interface has words for.
    expect(
      installMessage({
        type: "error",
        message: "backend prose",
        code: "too_big",
      })
    ).toBe("This build is too big for this computer. Pick a smaller one.")
    expect(
      installMessage({
        type: "queued",
        message: "backend prose",
        code: "queued",
      })
    ).toBe("Waiting for the download ahead of it")
  })

  it("falls back to the backend's sentence for a code it does not know", () => {
    // A newer backend, or a stage this build has never seen, still says
    // something.
    expect(
      installMessage({
        type: "error",
        message: "The embedder returned no vectors.",
        code: "not_shipped_yet",
      })
    ).toBe("The embedder returned no vectors.")
    expect(
      installMessage({ type: "error", message: "No code at all.", code: null })
    ).toBe("No code at all.")
    expect(installMessage({ type: "error", message: "Before codes." })).toBe(
      "Before codes."
    )
  })

  it("formats the disk refusal's raw numbers itself", () => {
    // The backend's sentence carries "5.0 GB", which no other language can
    // re-space or re-punctuate.
    expect(
      installMessage({
        type: "error",
        message: "This download needs 5.0 GB free; this computer has 2.1 GB.",
        code: "not_enough_disk",
        needed_bytes: 5_000_000_000,
        free_bytes: 2_140_000_000,
      })
    ).toBe("This download needs 5 GB free; this computer has 2.1 GB.")
  })

  it("keeps the backend's sentence when the disk refusal lacks a number", () => {
    const message = "This download needs 5.0 GB free; this computer has 2.1 GB."

    expect(
      installMessage({ type: "error", message, code: "not_enough_disk" })
    ).toBe(message)
    expect(
      installMessage({
        type: "error",
        message,
        code: "not_enough_disk",
        needed_bytes: 5_000_000_000,
      })
    ).toBe(message)
    expect(
      installMessage({
        type: "error",
        message,
        code: "not_enough_disk",
        free_bytes: 2_140_000_000,
      })
    ).toBe(message)
  })

  it("says nothing for an event with neither a code nor a message", () => {
    expect(installMessage({ type: "verifying" })).toBe("")
  })
})
