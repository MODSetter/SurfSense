import { describe, expect, it } from "vitest"

import { preprocessCitationMarkdown } from "./citation-markdown"

describe("preprocessCitationMarkdown", () => {
  it("turns explicit source citations into inline elements", () => {
    expect(preprocessCitationMarkdown("Claim [citation:2].")).toBe(
      'Claim <citation data-source-id="2">2</citation>.'
    )
  })

  it("leaves citation-shaped code and legacy ordinals unchanged", () => {
    const markdown = "Legacy [1]. Use `[citation:2]`.\n```\n[citation:3]\n```\n"

    expect(preprocessCitationMarkdown(markdown)).toBe(markdown)
  })
})
