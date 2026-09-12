import { describe, expect, it, vi } from "vitest"
import { fireEvent, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import { preprocessCitationMarkdown } from "./citation-markdown"
import { CitationProvider, InlineCitation } from "./inline-citation"

const catalog = [
  {
    source_id: 1,
    chunk_id: 30,
    document_id: 20,
    start_line: 1,
    end_line: 2,
    title: "Guide.txt",
  },
]

describe("preprocessCitationMarkdown", () => {
  it("turns explicit source citations into chunk chips", () => {
    expect(preprocessCitationMarkdown("Claim [citation:2].")).toBe(
      'Claim <citation data-chunk-id="2">2</citation>.'
    )
  })

  it("rewrites a catalog ordinal to the chunk id", () => {
    expect(preprocessCitationMarkdown("Claim [1].", catalog)).toBe(
      'Claim <citation data-chunk-id="30">30</citation>.'
    )
  })

  it("rewrites the old source-id wrapper through the catalog", () => {
    expect(preprocessCitationMarkdown("Claim [citation:1].", catalog)).toBe(
      'Claim <citation data-chunk-id="30">30</citation>.'
    )
  })

  it("leaves citation-shaped code and unknown ordinals unchanged", () => {
    const markdown = "Legacy [9]. Use `[citation:2]`.\n```\n[citation:3]\n```\n"

    expect(preprocessCitationMarkdown(markdown, catalog)).toBe(markdown)
  })
})

describe("InlineCitation", () => {
  it("opens the cited chunk on click", () => {
    const onCitation = vi.fn()

    render(
      <CitationProvider citations={catalog} onCitation={onCitation}>
        <InlineCitation data-chunk-id="30">30</InlineCitation>
      </CitationProvider>
    )

    fireEvent.click(
      screen.getByRole("button", { name: "View cited chunk 30" })
    )
    expect(onCitation).toHaveBeenCalledWith(30)
  })
})
