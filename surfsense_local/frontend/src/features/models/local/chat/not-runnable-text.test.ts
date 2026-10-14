import { describe, expect, it } from "vitest"

import { notRunnableLine, notRunnableReason } from "./not-runnable-text"

// `NotRunnableCode` in the backend's modules/llm/catalog/local/classifier.py,
// then `NotAnEmbedderCode` in modules/embedding/huggingface/pick.py.
const CODES = [
  "embedder",
  "speech_out",
  "speech_in",
  "audio_cpp",
  "labeller",
  "ocr",
  "drafter",
  "projector",
  "not_weights",
  "image",
  "image_edit",
  "video",
  "unsupported",
  "repo_gated",
  "repo_no_onnx",
  "repo_no_tokenizer",
  "repo_scan_flagged",
]

describe("why a row cannot run", () => {
  it("words a code it knows itself", () => {
    // The backend's sentence is English in every language.
    expect(
      notRunnableReason({
        not_runnable_code: "image",
        not_runnable_reason: "backend prose",
      })
    ).toBe(
      "This model makes pictures. SurfSense cannot run it from search yet."
    )
    expect(
      notRunnableReason({
        not_runnable_code: "unsupported",
        not_runnable_reason: "backend prose",
      })
    ).toBe("SurfSense cannot run this model.")
  })

  it("has a line of its own for every code the backend sends", () => {
    const lines = CODES.map((code) => notRunnableLine(code))

    expect(lines.every((line) => line)).toBe(true)
    expect(new Set(lines).size).toBe(CODES.length)
  })

  it("words an opened embedder repo's refusal itself", () => {
    expect(
      notRunnableReason({
        not_runnable_code: "repo_no_onnx",
        not_runnable_reason: "backend prose",
      })
    ).toBe("This repo has no ONNX build SurfSense can run.")
    expect(
      notRunnableReason({
        not_runnable_code: "repo_scan_flagged",
        not_runnable_reason: "backend prose",
      })
    ).toBe("Hugging Face’s security scan flags this repo.")
  })

  it("keeps the backend's sentence for a reason with no code", () => {
    // The one embedder refusal that names a file carries no code.
    const reason = "Hugging Face lists no checksum for onnx/model.onnx."

    expect(
      notRunnableReason({
        not_runnable_code: null,
        not_runnable_reason: reason,
      })
    ).toBe(reason)
    expect(notRunnableReason({ not_runnable_reason: reason })).toBe(reason)
  })

  it("keeps the backend's sentence for a code it does not know", () => {
    expect(
      notRunnableReason({
        not_runnable_code: "not_shipped_yet",
        not_runnable_reason: "A newer backend says why.",
      })
    ).toBe("A newer backend says why.")
    // A name every object has is not a code.
    expect(notRunnableLine("toString")).toBeNull()
  })

  it("says nothing for a row that runs", () => {
    expect(
      notRunnableReason({ not_runnable_code: null, not_runnable_reason: null })
    ).toBeNull()
  })
})
