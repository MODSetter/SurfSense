import { describe, expect, it } from "vitest"

import { getFileViewer } from "./registry"

describe("source file viewers", () => {
  it("provides the PDF viewer and leaves unsupported MIME types native", () => {
    expect(getFileViewer("application/pdf")).not.toBeNull()
    expect(getFileViewer("text/plain")).toBeNull()
    expect(getFileViewer(null)).toBeNull()
  })
})
