import { afterEach, describe, expect, it } from "vitest"
import { cleanup, fireEvent, screen } from "@testing-library/react"

import { render } from "@/test-utils"

import { ReplyThinking } from "./reply-thinking"

afterEach(cleanup)

describe("ReplyThinking", () => {
  it("says the model is working before anything has streamed", () => {
    render(<ReplyThinking running answerStarted={false} reasoning={null} />)

    expect(screen.getByRole("status").textContent).toBe("Thinking")
  })

  it("keeps the same header when the trace starts, so its motion never restarts", () => {
    const { container, rerender } = render(
      <ReplyThinking running answerStarted={false} reasoning={null} />
    )
    const header = screen.getByRole("button", { name: "Thinking" })
    const indicator = container.querySelector("svg")

    rerender(
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={{ text: "First step.", durationMs: null }}
      />
    )

    expect(screen.getByRole("button", { name: "Thinking" })).toBe(header)
    expect(container.querySelector("svg")).toBe(indicator)
  })

  it("shows nothing for a reply that answered without thinking", () => {
    const { container } = render(
      <ReplyThinking running answerStarted reasoning={null} />
    )

    expect(container.innerHTML).toBe("")
  })

  it("streams the trace open while the model thinks", () => {
    render(
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={{ text: "The note says revenue climbed.", durationMs: null }}
      />
    )

    const toggle = screen.getByRole("button", { name: "Thinking" })
    expect(toggle.getAttribute("aria-expanded")).toBe("true")
    expect(
      screen.getByRole("region", { name: "Thinking" }).textContent
    ).toContain("The note says revenue climbed.")
  })

  it("folds the trace away once the answer starts, and opens on click", () => {
    render(
      <ReplyThinking
        running
        answerStarted
        reasoning={{
          text: "The note says revenue climbed.",
          durationMs: 12_400,
        }}
      />
    )

    const toggle = screen.getByRole("button", {
      name: "Thought for 12 seconds",
    })
    expect(toggle.getAttribute("aria-expanded")).toBe("false")
    // Stays mounted so it can slide shut, but out of reach while folded.
    expect(screen.queryByRole("region")).toBeNull()

    fireEvent.click(toggle)

    expect(toggle.getAttribute("aria-expanded")).toBe("true")
    expect(
      screen.getByRole("region", { name: "Thought for 12 seconds" }).textContent
    ).toContain("The note says revenue climbed.")
  })

  it("holds the chat still while the trace slides open or shut", () => {
    render(
      <div data-testid="chat" style={{ overflowY: "auto" }}>
        <ReplyThinking
          running={false}
          answerStarted
          reasoning={{ text: "Earlier reasoning.", durationMs: 3_000 }}
        />
      </div>
    )
    const chat = screen.getByTestId("chat")
    chat.scrollTop = 200

    fireEvent.click(
      screen.getByRole("button", { name: "Thought for 3 seconds" })
    )
    // The chat's auto-scroll chasing the growing trace to the bottom.
    chat.scrollTop = 900
    fireEvent.scroll(chat)

    expect(chat.scrollTop).toBe(200)
  })

  it("keeps the newest reasoning in view while it streams", () => {
    const { rerender } = render(streaming("First step."))
    const trace = screen.getByText("First step.")
    layOut(trace, { scrollHeight: 400, clientHeight: 100, scrollTop: 0 })

    rerender(streaming("First step. Second step."))

    expect(trace.scrollTop).toBe(400)
  })

  it("stops following once the reader scrolls up to read", () => {
    const { rerender } = render(streaming("First step."))
    const trace = screen.getByText("First step.")
    layOut(trace, { scrollHeight: 400, clientHeight: 100, scrollTop: 100 })
    fireEvent.scroll(trace)

    layOut(trace, { scrollHeight: 600, clientHeight: 100, scrollTop: 100 })
    rerender(streaming("First step. Second step."))

    expect(trace.scrollTop).toBe(100)
  })
})

function streaming(text: string) {
  return (
    <ReplyThinking
      running
      answerStarted={false}
      reasoning={{ text, durationMs: null }}
    />
  )
}

// jsdom has no layout, so a test states the box it would have measured.
function layOut(
  element: HTMLElement,
  box: { scrollHeight: number; clientHeight: number; scrollTop: number }
) {
  for (const [name, value] of Object.entries(box)) {
    Object.defineProperty(element, name, {
      value,
      writable: true,
      configurable: true,
    })
  }
}
