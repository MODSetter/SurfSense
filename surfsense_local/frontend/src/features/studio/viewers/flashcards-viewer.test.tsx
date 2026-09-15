import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"

import { FlashcardsViewer, type FlashcardDeck } from "./flashcards-viewer"

const deck: FlashcardDeck = {
  schema_version: 1,
  title: "Cassini",
  cards: [
    { front_text: "Arrival at Saturn?", back_text: "2004" },
    { front_text: "Mission end?", back_text: "2017" },
  ],
}

afterEach(cleanup)

describe("flashcards viewer", () => {
  it("shows one card at a time, front first, and reveals the back on demand", async () => {
    const user = userEvent.setup()
    render(<FlashcardsViewer deck={deck} />)

    expect(screen.getByText("Arrival at Saturn?")).toBeTruthy()
    expect(screen.queryByText("2004")).toBeNull()
    expect(screen.getByText("1 / 2")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Reveal answer" }))
    expect(screen.getByText("2004")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Next card" }))
    expect(screen.getByText("Mission end?")).toBeTruthy()
    expect(screen.queryByText("2017")).toBeNull()
    expect(screen.getByText("2 / 2")).toBeTruthy()
  })

  it("keeps score with Got it / Again and replays the missed cards", async () => {
    const user = userEvent.setup()
    render(<FlashcardsViewer deck={deck} />)

    // Marks only make sense once the answer is seen.
    expect(screen.queryByRole("button", { name: "Got it" })).toBeNull()
    await user.click(screen.getByRole("button", { name: "Reveal answer" }))
    await user.click(screen.getByRole("button", { name: "Again" }))
    expect(screen.getByText("Mission end?")).toBeTruthy()
    expect(screen.getByText("0 got it · 1 again")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Reveal answer" }))
    await user.click(screen.getByRole("button", { name: "Got it" }))
    expect(screen.getByText("1 got it · 1 again")).toBeTruthy()
    expect(screen.getByText("1 of 2 known")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Review 1 again" }))
    expect(screen.getByText("Arrival at Saturn?")).toBeTruthy()
    expect(screen.getByText("1 / 1")).toBeTruthy()
  })
})
