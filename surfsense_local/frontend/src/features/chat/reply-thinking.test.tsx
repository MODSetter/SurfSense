import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  render as renderAtRoot,
  screen,
  waitFor,
} from "@testing-library/react"
import { tailBoundedRemend } from "@assistant-ui/react-streamdown"
import { StrictMode } from "react"
import { Streamdown } from "streamdown"

import {
  STREAMDOWN_LINK_SAFETY,
  streamdownPlugins,
  streamingStreamdownPlugins,
} from "@/features/studio/viewers/streamdown-config"
import { render } from "@/test-utils"

import { ReplyThinking } from "./reply-thinking"

const seen = vi.hoisted(() => ({ trace: [] as Record<string, unknown>[] }))

// Records what each Streamdown render is given; renders the real one.
vi.mock("streamdown", async (original) => {
  const actual = (await original()) as Record<string, unknown>
  const React = await import("react")
  const Real = actual.Streamdown as React.ComponentType<Record<string, unknown>>
  return {
    ...actual,
    Streamdown: (props: Record<string, unknown>) => {
      seen.trace.push(props)
      return React.createElement(Real, props)
    },
  }
})

beforeEach(() => {
  seen.trace = []
})

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

  it("keeps the newest reasoning in view while it streams", async () => {
    const { rerender } = render(streaming("First step."))
    const trace = screen.getByRole("region", { name: "Thinking" })
    await nextFrame()
    layOut(trace, { scrollHeight: 400, clientHeight: 100, scrollTop: 0 })

    rerender(streaming("First step. Second step."))
    await nextFrame()

    expect(trace.scrollTop).toBe(400)
  })

  it("stops following once the reader scrolls up to read", async () => {
    const { rerender } = render(streaming("First step."))
    const trace = screen.getByRole("region", { name: "Thinking" })
    await nextFrame()
    layOut(trace, { scrollHeight: 400, clientHeight: 100, scrollTop: 100 })
    fireEvent.scroll(trace)

    layOut(trace, { scrollHeight: 600, clientHeight: 100, scrollTop: 100 })
    rerender(streaming("First step. Second step."))
    await nextFrame()

    expect(trace.scrollTop).toBe(100)
  })

  it("keeps following after StrictMode remounts its effects, as in development", async () => {
    const strict = (text: string) => <StrictMode>{streaming(text)}</StrictMode>
    // At the root, as main.tsx has it: StrictMode inside a newly mounted
    // wrapper does not remount effects.
    const { rerender } = renderAtRoot(strict("First step."))
    const trace = screen.getByRole("region", { name: "Thinking" })
    await nextFrame()
    layOut(trace, { scrollHeight: 400, clientHeight: 100, scrollTop: 0 })

    rerender(strict("First step. Second step."))
    await nextFrame()

    expect(trace.scrollTop).toBe(400)
  })

  it("lays the trace out once a frame, however many tokens arrive in it", async () => {
    const { rerender } = render(streaming("Step"))
    const trace = screen.getByRole("region", { name: "Thinking" })
    await nextFrame()
    const layouts = measured(trace)

    for (let token = 1; token <= 5; token += 1) {
      rerender(streaming(`Step ${token}`))
    }
    await nextFrame()

    expect(layouts()).toBe(1)
    expect(trace.scrollTop).toBe(400)
  })

  it("does not lay out a folded trace", async () => {
    const { container, rerender } = render(finished("Earlier reasoning."))
    await nextFrame()
    const layouts = measured(traceIn(container))

    rerender(finished("Earlier reasoning, revised."))
    await nextFrame()

    expect(layouts()).toBe(0)
  })
})

describe("the trace's markdown", () => {
  it("repairs only the unfinished tail, and Streamdown repairs nothing again", () => {
    const text = "## Plan\n\nRead the note.\n\nThen **compare"
    render(streaming(text))

    const props = seen.trace[seen.trace.length - 1]
    expect(props.parseIncompleteMarkdown).toBe(false)
    expect(props.children).toBe(tailBoundedRemend(text))
  })

  it("keeps its options across tokens, so a token never redraws the whole trace", () => {
    const { rerender } = render(streaming("First step."))
    const first = seen.trace[seen.trace.length - 1]

    rerender(streaming("First step. Second step."))
    const last = seen.trace[seen.trace.length - 1]

    expect(last.linkSafety).toBe(first.linkSafety)
    expect(last.plugins).toBe(first.plugins)
  })

  it("colours code only once thinking is done, with the same math plugin", () => {
    const text = "Try:\n\n```ts\nconst a = 1\n```"
    const { rerender } = render(streaming(text))
    const thinking = seen.trace[seen.trace.length - 1].plugins as Plugins

    rerender(finished(text))
    const done = seen.trace[seen.trace.length - 1].plugins as Plugins

    expect(thinking.code).toBeUndefined()
    expect(done.code).toBeDefined()
    expect(done.math).toBe(thinking.math)
  })

  describe.each([
    ["an unclosed bold", "Plan first.\n\nThen **compare the quarters"],
    ["an open code fence", "Plan first.\n\n```ts\nconst total = 3\nconst"],
    ["an unclosed math block", "Plan first.\n\n$$\n\\sum_{k=1}^{n} k"],
  ])("ending in %s", (_ending, text) => {
    // Streamdown's own repair of the whole trace, as the trace had it.
    const reference = (plugins: object) =>
      render(
        <Streamdown plugins={plugins} linkSafety={STREAMDOWN_LINK_SAFETY}>
          {text}
        </Streamdown>
      ).container.firstElementChild!

    it("renders as before while thinking", () => {
      const expected = reference(streamingStreamdownPlugins)
      const { container } = render(streaming(text))

      expect(traceIn(container).firstElementChild?.innerHTML).toBe(
        expected.innerHTML
      )
    })

    it("renders as before once done", async () => {
      const expected = reference(streamdownPlugins)
      const { container } = render(finished(text))

      // Coloured code lands a moment later, in both.
      await waitFor(() =>
        expect(traceIn(container).firstElementChild?.innerHTML).toBe(
          expected.innerHTML
        )
      )
    })
  })
})

type Plugins = { code?: unknown; math?: unknown }

function finished(text: string) {
  return (
    <ReplyThinking
      running
      answerStarted
      reasoning={{ text, durationMs: 2_000 }}
    />
  )
}

/** The trace box, open or folded (a folded one is hidden from roles). */
function traceIn(container: HTMLElement) {
  return container.querySelector<HTMLElement>('[role="region"]')!
}

// The trace follows on the next frame, not in the render that changed it.
function nextFrame() {
  return act(
    () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  )
}

/** Lays the trace out as 400px of content in a 100px box, and counts the
 *  reads of its height, each one a layout in a browser. */
function measured(element: HTMLElement) {
  let reads = 0
  layOut(element, { scrollHeight: 400, clientHeight: 100, scrollTop: 0 })
  Object.defineProperty(element, "scrollHeight", {
    configurable: true,
    get: () => {
      reads += 1
      return 400
    },
  })
  return () => reads
}

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
