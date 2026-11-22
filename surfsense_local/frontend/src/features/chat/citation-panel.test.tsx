import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"

import { render } from "@/test-utils"

import { CitationPanel } from "./citation-panel"

const LONG_LINK = `https://thumb.wikimedia.org/${"World_hydro_generation_".repeat(12)}.png`

function showChunk(content: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        id: 7,
        title: "Hydroelectricity - Wikipedia",
        document_type: "NOTE",
        total_chunks: 1,
        chunk_start_index: 0,
        chunks: [{ id: 214, content }],
      })
    )
  )
  render(
    <CitationPanel
      workspaceId={1}
      chunkId={214}
      onClose={() => undefined}
      onOpen={() => undefined}
    />
  )
  return screen.findByText("Cited chunk")
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("a cited chunk", () => {
  it("reads as formatted text, not as markdown", async () => {
    await showChunk(
      "## Hydro power\n\n[China](https://en.wikipedia.org/wiki/China) produced **the most**."
    )

    expect(screen.getByRole("heading", { name: "Hydro power" })).toBeTruthy()
    expect(document.body.textContent).toContain("China produced the most.")
    expect(document.body.textContent).not.toContain("](https://")
    expect(document.body.textContent).not.toContain("**")
    expect(screen.getByText("the most").tagName).not.toBe("P")
  })

  it("never loads a chunk's remote image, or shows its address", async () => {
    await showChunk(`Before\n\n![](${LONG_LINK})\n\nAfter`)

    await screen.findByText("After")
    expect(document.querySelector("img")).toBeNull()
    expect(document.body.textContent).not.toContain("wikimedia")
    expect(document.body.textContent).not.toContain("blocked")
    // No gap is left where it stood.
    const paragraphs = [...document.querySelectorAll("p")].map(
      (p) => p.textContent
    )
    expect(paragraphs).not.toContain("")
  })

  it("names an image only by what its source calls it", async () => {
    await showChunk(`Before\n\n![Output by year](${LONG_LINK})\n\nAfter`)

    await screen.findByText("Output by year")
    expect(document.querySelector("img")).toBeNull()
    expect(document.body.textContent).not.toContain("wikimedia")
    expect(document.body.textContent).not.toContain("blocked")
  })

  it("takes an image written as HTML the same way", async () => {
    await showChunk(`Before\n\n<img src="${LONG_LINK}" alt="A dam">\n\nAfter`)

    await screen.findByText("After")
    expect(document.querySelector("img")).toBeNull()
    expect(document.body.textContent).not.toContain("blocked")
  })

  it("wraps text with no spaces inside its card", async () => {
    await showChunk(`See ${"unbroken".repeat(40)} there`)

    const text = await screen.findByText(/unbroken/)
    expect(text.closest("[class*='wrap-anywhere']")).toBeTruthy()
  })

  it("takes no script from a chunk", async () => {
    await showChunk("Safe<script>window.hacked = true</script> text")

    await waitFor(() => expect(document.body.textContent).toContain("Safe"))
    expect(document.querySelector("script")).toBeNull()
  })

  it("shows a chunk cut off inside its formatting without breaking", async () => {
    await showChunk("Starts **bold and never ends\n\n| a | b |\n| - |")

    expect(document.body.textContent).toContain("bold and never ends")
  })
})
