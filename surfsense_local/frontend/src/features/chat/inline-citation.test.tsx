import { memo, useLayoutEffect } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import { useCitationContext } from "./citation-context"
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

afterEach(cleanup)

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

    fireEvent.click(screen.getByRole("button", { name: "View cited chunk 30" }))
    expect(onCitation).toHaveBeenCalledWith(30)
  })

  it("re-renders no reply for a new handler, and opens with the newest", () => {
    const renders = vi.fn()
    // Stands for a reply's markdown, which reads the citations from context.
    const Reply = memo(function Reply() {
      useCitationContext()
      renders()
      return <InlineCitation data-chunk-id="30">30</InlineCitation>
    })
    const first = vi.fn()
    const latest = vi.fn()

    const { rerender } = render(
      <CitationProvider citations={catalog} onCitation={first}>
        <Reply />
      </CitationProvider>
    )
    rerender(
      <CitationProvider citations={catalog} onCitation={latest}>
        <Reply />
      </CitationProvider>
    )
    fireEvent.click(screen.getByRole("button", { name: "View cited chunk 30" }))

    expect(renders).toHaveBeenCalledTimes(1)
    expect(latest).toHaveBeenCalledWith(30)
    expect(first).not.toHaveBeenCalled()
  })

  it("gives a child's layout effect the handler of its own commit", () => {
    // A parent's layout effects run after its children's.
    function OpensOnMount({ chunkId }: { chunkId: number }) {
      const context = useCitationContext()
      useLayoutEffect(() => context?.onCitation(chunkId), [context, chunkId])
      return null
    }
    const first = vi.fn()
    const latest = vi.fn()

    const { rerender } = render(
      <CitationProvider citations={catalog} onCitation={first}>
        <OpensOnMount chunkId={30} />
      </CitationProvider>
    )
    rerender(
      <CitationProvider citations={catalog} onCitation={latest}>
        <OpensOnMount chunkId={31} />
      </CitationProvider>
    )

    expect(first.mock.calls).toEqual([[30]])
    expect(latest.mock.calls).toEqual([[31]])
  })
})
