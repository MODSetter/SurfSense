import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ArtifactPanel } from "./artifact-panel"
import { useStudio } from "./use-studio"

function summary(content: string, generation: number) {
  return {
    id: 12,
    document_id: 4,
    format: "summary",
    generation,
    title: "Weekly summary",
    status: "ready",
    error_message: null,
    content,
    files: [],
    created_at: "2026-09-06T00:00:00Z",
    updated_at: "2026-09-06T00:00:00Z",
  }
}

/** The Studio list and an open artifact, as the dashboard shows them. */
function OpenArtifact() {
  useStudio(1)
  return <ArtifactPanel artifactId={12} onClose={vi.fn()} />
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("artifact panel", () => {
  it("loads an artifact into the detail rail", async () => {
    const onClose = vi.fn()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/artifacts/12") {
          return Response.json({
            id: 12,
            document_id: 4,
            format: "summary",
            generation: 1,
            title: "Weekly summary",
            status: "ready",
            error_message: null,
            content: "Saturn is a gas giant.",
            files: [
              {
                role: "primary",
                mime_type: "text/markdown",
                size_bytes: 24,
                original_filename: "summary.md",
              },
            ],
            created_at: "2026-09-06T00:00:00Z",
            updated_at: "2026-09-06T00:00:00Z",
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(<ArtifactPanel artifactId={12} onClose={onClose} />)

    expect(
      await screen.findByRole("complementary", { name: "Artifact" })
    ).toBeTruthy()
    expect(await screen.findByText("Weekly summary")).toBeTruthy()
    expect(screen.getByText("Saturn is a gas giant.")).toBeTruthy()
    // The API is another origin, where `download` is ignored: the server
    // itself must say attachment, or the file opens in a window.
    expect(
      screen.getByRole("link", { name: "Download" }).getAttribute("href")
    ).toMatch(/\/artifacts\/12\/files\/primary\?download=1$/)
    await user.click(screen.getByRole("button", { name: "Close artifact" }))
    expect(onClose).toHaveBeenCalled()
  })

  it("opens flashcards in the study viewer from the deck file", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/artifacts/13") {
          return Response.json({
            id: 13,
            document_id: 5,
            format: "flashcards",
            generation: 1,
            title: "Cassini",
            status: "ready",
            error_message: null,
            content: "# Cassini\n\n**1. Arrival?**\n\n2004",
            files: [
              {
                role: "primary",
                mime_type: "application/json",
                size_bytes: 90,
                original_filename: "cassini.json",
              },
            ],
            created_at: "2026-09-06T00:00:00Z",
            updated_at: "2026-09-06T00:00:00Z",
          })
        }
        if (path === "/artifacts/13/files/primary") {
          return Response.json({
            schema_version: 1,
            title: "Cassini",
            cards: [{ front_text: "Arrival?", back_text: "2004" }],
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )

    render(<ArtifactPanel artifactId={13} onClose={vi.fn()} />)

    expect(
      await screen.findByRole("button", { name: "Reveal answer" })
    ).toBeTruthy()
    expect(screen.getByText("Arrival?")).toBeTruthy()
    // The markdown body is for search, not for the study screen.
    expect(screen.queryByText(/\*\*1\. Arrival\?\*\*/)).toBeNull()
  })

  it("shows a regenerated artifact once the workspace says it changed", async () => {
    let feed!: ReadableStreamDefaultController<Uint8Array>
    const events = new ReadableStream<Uint8Array>({
      start(controller) {
        feed = controller
      },
    })
    let generation = 1
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path.endsWith("/events")) {
          return new Response(events, {
            headers: { "Content-Type": "text/event-stream" },
          })
        }
        if (path.includes("/studio/formats")) return Response.json([])
        if (path === "/workspaces/1/artifacts") return Response.json([])
        if (path === "/artifacts/12") {
          return Response.json(
            generation === 1
              ? summary("Saturn is a gas giant.", 1)
              : summary("Saturn has 274 moons.", 2)
          )
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )

    render(<OpenArtifact />)
    expect(await screen.findByText("Saturn is a gas giant.")).toBeTruthy()
    generation = 2
    const encoder = new TextEncoder()
    feed.enqueue(encoder.encode(": connected\n\n"))
    feed.enqueue(
      encoder.encode(
        'event: artifacts\ndata: {"ids": [12], "status": "ready"}\n\n'
      )
    )

    // The same event that reloads the list reloads what is open from it.
    expect(await screen.findByText("Saturn has 274 moons.")).toBeTruthy()
  })
})
