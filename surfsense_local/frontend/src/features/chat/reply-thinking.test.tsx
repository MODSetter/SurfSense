import { afterEach, describe, expect, it } from "vitest"
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"

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

  it("shows how much of a long prompt has been read while it waits", () => {
    const { rerender } = render(
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={null}
        progress={{ processed: 2048, total: 4096 }}
      />
    )
    const header = screen.getByRole("button", { name: "Reading 50%" })

    rerender(
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={null}
        progress={{ processed: 3072, total: 4096 }}
      />
    )

    // The same header, so its motion never restarts as the figure moves.
    expect(screen.getByRole("button", { name: "Reading 75%" })).toBe(header)
  })

  it("has no figure to show before reading starts or once it is done", () => {
    const { rerender } = render(
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={null}
        progress={{ processed: 0, total: 4096 }}
      />
    )
    expect(screen.getByRole("button", { name: "Thinking" })).toBeTruthy()

    rerender(
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={null}
        progress={{ processed: 4096, total: 4096 }}
      />
    )
    expect(screen.getByRole("button", { name: "Thinking" })).toBeTruthy()
  })

  it("announces reading by quarters, not at every update", () => {
    const at = (processed: number) => (
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={null}
        progress={{ processed, total: 1000 }}
      />
    )
    const { rerender } = render(at(100))
    const status = screen.getByRole("status")
    expect(status.textContent).toBe("Thinking")

    rerender(at(300))
    expect(status.textContent).toBe("Reading 25%")
    rerender(at(450))
    expect(status.textContent).toBe("Reading 25%")
    rerender(at(600))
    expect(status.textContent).toBe("Reading 50%")
    expect(screen.getByRole("button", { name: "Reading 60%" })).toBeTruthy()
  })

  it("drops the figure once the trace starts", () => {
    render(
      <ReplyThinking
        running
        answerStarted={false}
        reasoning={{ text: "First step.", durationMs: null }}
        progress={{ processed: 2048, total: 4096 }}
      />
    )

    expect(screen.getByRole("button", { name: "Thinking" })).toBeTruthy()
    expect(screen.getByRole("status").textContent).toBe("Thinking")
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

  it("renders the trace as markdown, not as literal syntax", async () => {
    render(
      streaming(
        "## Plan\n\n- read the note\n- **compare** the quarters\n\n```\nrevenue = 3\n```"
      )
    )
    const trace = screen.getByRole("region", { name: "Thinking" })

    expect(trace.querySelector("h2")?.textContent).toBe("Plan")
    expect(trace.querySelectorAll("li")).toHaveLength(2)
    // Streamdown renders emphasis as a styled span, not a <strong>.
    expect(trace.querySelector('[data-streamdown="strong"]')?.textContent).toBe(
      "compare"
    )
    await waitFor(() =>
      expect(trace.querySelector("code")?.textContent).toContain("revenue = 3")
    )
    expect(trace.textContent).not.toContain("##")
    expect(trace.textContent).not.toContain("**")
  })

  it("carries the answer's link and image limits", () => {
    render(
      streaming(
        "[run](javascript:alert(1)) ![pic](data:image/png;base64,AAAA) [docs](https://example.com)"
      )
    )
    const trace = screen.getByRole("region", { name: "Thinking" })

    // The one link left is the https one; Streamdown's link safety renders
    // it as a button that asks before leaving. The rest is blocked into text.
    const links = trace.querySelectorAll('[data-streamdown="link"]')
    expect(links).toHaveLength(1)
    expect(links[0]?.textContent).toBe("docs")
    expect(trace.querySelector('a[href^="javascript:"]')).toBeNull()
    expect(trace.textContent).toContain("run [blocked]")
    expect(trace.querySelector("img")).toBeNull()
    expect(trace.textContent).toContain("Image blocked")
  })

  it("keeps the newest reasoning in view while it streams", () => {
    const { rerender } = render(streaming("First step."))
    const trace = screen.getByRole("region", { name: "Thinking" })
    layOut(trace, { scrollHeight: 400, clientHeight: 100, scrollTop: 0 })

    rerender(streaming("First step. Second step."))

    expect(trace.scrollTop).toBe(400)
  })

  it("stops following once the reader scrolls up to read", () => {
    const { rerender } = render(streaming("First step."))
    const trace = screen.getByRole("region", { name: "Thinking" })
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
