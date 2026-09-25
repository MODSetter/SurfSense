import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"
import type { ArtifactDetail, FlashcardState } from "../../api"
import { FlashcardsViewer } from "./flashcards-viewer"

const deckFile = {
  schema_version: 1,
  title: "Cassini",
  cards: [
    { front_text: "Arrival year?", back_text: "2004" },
    { front_text: "Mission end year?", back_text: "2017" },
  ],
}

const artifact: ArtifactDetail = {
  id: 1,
  document_id: 1,
  format: "flashcards",
  generation: 1,
  title: "Cassini",
  status: "ready",
  error_message: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  content: null,
  files: [
    {
      role: "primary",
      mime_type: "application/json",
      size_bytes: 200,
      original_filename: "cassini.json",
    },
  ],
  quiz_state: null,
  flashcard_state: null,
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("flashcards viewer", () => {
  it("flips a card, marks it, and persists the mark against the server", async () => {
    // A minimal stand-in for the real flashcard-state endpoints (see
    // backend/modules/artifacts/flashcard_progress.py), just enough to
    // prove the viewer round-trips through PUT/GET rather than mutating
    // local state.
    let state: FlashcardState = { generation: 1, marks: {}, order: [0, 1] }

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === "/artifacts/1/files/primary") {
          return Response.json(deckFile)
        }
        if (
          url === "/artifacts/1/flashcard-state/mark" &&
          init?.method === "PUT"
        ) {
          const body = JSON.parse(init.body as string)
          state = {
            ...state,
            marks: { ...state.marks, [body.card_index]: body.mark },
          }
          return Response.json(state)
        }
        throw new Error(`unhandled request: ${url}`)
      })
    )

    const user = userEvent.setup()
    render(<FlashcardsViewer artifact={artifact} actionsContainer={null} />)

    expect(await screen.findByText("Arrival year?")).toBeTruthy()
    // Card 1 of 2: assistive tech hears how far through the deck this is.
    expect(
      screen
        .getByRole("progressbar", { name: "Deck progress" })
        .getAttribute("aria-valuenow")
    ).toBe("50")
    // Both faces mount for the flip transition; only the front is exposed
    // to assistive tech until revealed.
    expect(
      screen
        .getByText("2004")
        .closest("[aria-hidden]")
        ?.getAttribute("aria-hidden")
    ).toBe("true")

    await user.click(screen.getByRole("button", { name: "Reveal answer" }))
    expect(
      await screen.findByRole("button", { name: "Show question" })
    ).toBeTruthy()
    expect(
      screen
        .getByText("2004")
        .closest("[aria-hidden]")
        ?.getAttribute("aria-hidden")
    ).toBe("false")

    await user.click(screen.getByRole("button", { name: /Got it/ }))

    expect(await screen.findByText("Mission end year?")).toBeTruthy()
  })
})
