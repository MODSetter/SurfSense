import { describe, expect, it } from "vitest"

import { getFileViewer } from "./registry"

describe("source file viewers", () => {
  it("provides the PDF viewer and leaves unsupported MIME types native", () => {
    expect(getFileViewer("application/pdf")).not.toBeNull()
    expect(getFileViewer("text/plain")).toBeNull()
    expect(getFileViewer(null)).toBeNull()
  })

  it("previews no recording until an audio viewer exists", () => {
    for (const mimeType of [
      "audio/wav",
      "audio/mpeg",
      "audio/flac",
      "audio/ogg",
    ]) {
      expect(getFileViewer(mimeType)).toBeNull()
    }
  })
})
