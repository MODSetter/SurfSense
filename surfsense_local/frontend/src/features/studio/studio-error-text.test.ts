import { describe, expect, it } from "vitest"

import { ApiError } from "@/lib/api"

import { translatedStudioError } from "./studio-error-text"

describe("a refused Studio job", () => {
  // The codes `refused()` sends from modules/artifacts/refused.py.
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
    // And from a revised copy's Accept all or Reject all, revised_copies/.
    [
      "not_word_copy",
      "Only a Word revised copy has tracked changes to accept or reject.",
    ],
  ])("has its own line for %s", (code, line) => {
    const refusal = new ApiError(409, "backend prose, never shown", code)

    expect(translatedStudioError(refusal)).toBe(line)
  })

  it("formats the numbers a too-long rewrite sends beside its sentence", () => {
    const refusal = new ApiError(
      409,
      "backend prose, never shown",
      "rewrite_too_long",
      {
        message: "backend prose, never shown",
        code: "rewrite_too_long",
        model: "Qwen3-4B",
        spec_tokens: 12345,
        needed_tokens: 29300,
        window_tokens: 8192,
      }
    )

    expect(translatedStudioError(refusal)).toBe(
      "This document is too long for Qwen3-4B to rewrite in one go: it is about 12,345 tokens, and reading it and writing it again needs about 29,300 of the model’s 8,192-token window."
    )
  })

  it.each([
    ["no model", { spec_tokens: 1, needed_tokens: 2, window_tokens: 3 }],
    ["no document size", { model: "m", needed_tokens: 2, window_tokens: 3 }],
    ["no needed size", { model: "m", spec_tokens: 1, window_tokens: 3 }],
    ["no window", { model: "m", spec_tokens: 1, needed_tokens: 2 }],
    [
      "a number sent as text",
      { model: "m", spec_tokens: "1", needed_tokens: 2, window_tokens: 3 },
    ],
  ])(
    "leaves a too-long rewrite with %s to the backend's sentence",
    (_, values) => {
      const refusal = new ApiError(
        409,
        "the backend's own",
        "rewrite_too_long",
        {
          message: "the backend's own",
          code: "rewrite_too_long",
          ...values,
        }
      )

      expect(translatedStudioError(refusal)).toBeNull()
    }
  )

  it.each([
    ["no_tracked_changes", "Version 2 has no tracked changes to decide."],
    [
      "version_being_made",
      "Version 2 of this revised copy is still being made. Wait for it to finish, then revise again.",
    ],
  ])("puts the version a revised copy's %s sends in its line", (code, line) => {
    const refusal = new ApiError(409, "backend prose, never shown", code, {
      message: "backend prose, never shown",
      code,
      version: 2,
    })

    expect(translatedStudioError(refusal)).toBe(line)
  })

  it.each([
    ["no_tracked_changes", undefined],
    ["no_tracked_changes", "2"],
    ["version_being_made", undefined],
    ["version_being_made", "2"],
  ])(
    "leaves %s with the version %j to the backend's sentence",
    (code, version) => {
      const refusal = new ApiError(409, "the backend's own", code, {
        message: "the backend's own",
        code,
        version,
      })

      expect(translatedStudioError(refusal)).toBeNull()
    }
  )

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
