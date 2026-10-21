import { describe, expect, it } from "vitest"

import { ApiError } from "@/lib/api"

import { translatedStudioError } from "./studio-error-text"

describe("a refused Studio job", () => {
  // The codes `_refused()` sends from modules/artifacts/service.py.
  it.each([
    ["already_generating", "Already generating."],
    ["nothing_running", "Nothing is running."],
    ["no_sources", "Pick at least one source."],
    ["sources_indexing", "The chosen sources are still indexing."],
    ["sources_gone", "None of this artifact’s sources are left."],
    // And from a refine, modules/artifacts/studio_documents/service.py.
    [
      "not_refinable",
      "Only a Word document, PDF or web page made in Studio can be refined.",
    ],
    [
      "agent_made",
      "The agent made this document: ask for changes in its chat.",
    ],
    [
      "version_unfinished",
      "This version did not finish: retry it, or refine another version.",
    ],
  ])("has its own line for %s", (code, line) => {
    const refusal = new ApiError(409, "backend prose, never shown", code)

    expect(translatedStudioError(refusal)).toBe(line)
  })

  it("has none for a code it does not know, so the backend's sentence stays", () => {
    const refusal = new ApiError(
      409,
      "a chosen source is not in this workspace",
      "elsewhere"
    )

    expect(translatedStudioError(refusal)).toBeNull()
  })

  it("has none for a refusal without a code", () => {
    expect(
      translatedStudioError(new ApiError(409, "unknown format: zine"))
    ).toBeNull()
    expect(translatedStudioError(new Error("offline"))).toBeNull()
  })
})
