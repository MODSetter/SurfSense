import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from "vitest"
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

describe("following the trace in a browser's frame order", () => {
  const steps = (count: number) =>
    Array.from({ length: count }, (_, index) => `Step ${index + 1}.`).join(
      "\n\n"
    )

  /** A trace of `lines` lines, laid out as a browser would and followed to
   *  its bottom, with that scroll already reported. */
  function followedTrace(lines: number) {
    const frames = browserFrames()
    const shown = { lines }
    const { rerender } = render(streaming(steps(lines)))
    const trace = frames.lineBox(
      screen.getByRole("region", { name: "Thinking" }),
      () => shown.lines
    )
    const stream = {
      trace,
      next: frames.next,
      bottom: () => trace.scrollHeight - trace.clientHeight,
      grow() {
        shown.lines += 1
        rerender(streaming(steps(shown.lines)))
      },
    }
    // A line more, since jsdom had no layout until now.
    stream.grow()
    stream.next()
    stream.next()
    return stream
  }

  it("keeps following when a line lands before its own scroll is reported", () => {
    const stream = followedTrace(10)

    // A line a frame, each landing between the follow and its scroll event.
    for (let line = 0; line < 10; line += 1) {
      stream.grow()
      stream.next()
    }

    expect(stream.trace.scrollTop).toBe(stream.bottom())
  })

  it("stops while the reader is scrolled up, and follows again from the bottom", () => {
    const stream = followedTrace(10)

    stream.trace.scrollTop = 0
    stream.next()
    stream.grow()
    stream.next()
    expect(stream.trace.scrollTop).toBe(0)

    stream.trace.scrollTop = stream.bottom()
    stream.next()
    stream.grow()
    stream.next()
    expect(stream.trace.scrollTop).toBe(stream.bottom())
  })

  it("follows again when the reader comes back to where it left off", () => {
    const stream = followedTrace(10)
    const leftAt = stream.trace.scrollTop

    // Up and back while the model pauses, so the bottom has not moved.
    stream.trace.scrollTop = 0
    stream.next()
    stream.trace.scrollTop = leftAt
    stream.next()
    stream.grow()
    stream.next()

    expect(stream.trace.scrollTop).toBe(stream.bottom())
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

  // Where the trace's old whole-trace repair differed: it closed the earlier
  // paragraph's ** at the end of the trace, as literal asterisks.
  it("leaves a marker open in an earlier paragraph alone, as the answer does", () => {
    render(streaming("Some **bold\n\nmore text"))
    const trace = screen.getByRole("region", { name: "Thinking" })

    expect(trace.textContent).toBe("Some **boldmore text")
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

  it("keeps code plain while the trace grows after the answer has started", () => {
    // An agent reasons again after a tool call, under a header already done.
    const text = "Plan.\n\n```ts\nconst a = 1\n"
    const growing = (running: boolean, durationMs: number | null) => (
      <ReplyThinking
        running={running}
        answerStarted
        reasoning={{ text, durationMs }}
      />
    )
    const plugins = () => seen.trace[seen.trace.length - 1].plugins as Plugins
    const { rerender } = render(growing(true, null))
    const streamed = plugins()

    rerender(growing(true, 3_000))
    const ended = plugins()
    rerender(growing(false, null))
    const stopped = plugins()

    expect(streamed.code).toBeUndefined()
    expect(ended.code).toBeDefined()
    expect(stopped.code).toBeDefined()
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

describe("the thinking indicator", () => {
  it("is dropped once it has folded away, under the same header", async () => {
    const { container, rerender } = render(streaming("First step."))
    const header = screen.getByRole("button", { name: "Thinking" })

    rerender(finished("First step."))
    // Still there while it folds.
    expect(container.querySelector(".ss-thinking-indicator")).not.toBeNull()

    await waitFor(() =>
      expect(container.querySelector(".ss-thinking-indicator")).toBeNull()
    )
    expect(screen.getByRole("button", { name: "Thought for 2 seconds" })).toBe(
      header
    )
  })

  it("is never mounted for a reply that was done before it showed", () => {
    const { container } = render(finished("Earlier reasoning."))

    expect(container.querySelector(".ss-thinking-indicator")).toBeNull()
  })

  it("comes back the moment the header works again", () => {
    const { container, rerender } = render(finished("Earlier reasoning."))

    // A thread switch gives this header another thread's reply in progress.
    rerender(<ReplyThinking running answerStarted={false} reasoning={null} />)

    expect(container.querySelector(".ss-thinking-indicator")).not.toBeNull()
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

/** Runs frames in a browser's order, which jsdom has no notion of: a scroll
 *  made in one frame's callbacks is reported at the next frame, before that
 *  frame's callbacks run. */
function browserFrames() {
  const due = new Map<number, FrameRequestCallback>()
  let handle = 0
  const request = vi
    .spyOn(window, "requestAnimationFrame")
    .mockImplementation((callback) => {
      handle += 1
      due.set(handle, callback)
      return handle
    })
  const cancel = vi
    .spyOn(window, "cancelAnimationFrame")
    .mockImplementation((id) => {
      due.delete(id)
    })
  onTestFinished(() => {
    request.mockRestore()
    cancel.mockRestore()
  })
  const moved = new Set<HTMLElement>()

  return {
    /** Lays the element out as `lines()` lines of 24px in a 208px box, its
     *  scrollTop clamped as a browser clamps it. */
    lineBox(element: HTMLElement, lines: () => number) {
      let top = 0
      const height = () => lines() * 24
      Object.defineProperties(element, {
        clientHeight: { configurable: true, value: 208 },
        scrollHeight: { configurable: true, get: height },
        scrollTop: {
          configurable: true,
          get: () => top,
          set: (value: number) => {
            const clamped = Math.max(0, Math.min(value, height() - 208))
            if (clamped !== top) {
              top = clamped
              moved.add(element)
            }
          },
        },
      })
      return element
    },
    next() {
      act(() => {
        for (const element of moved) fireEvent.scroll(element)
        moved.clear()
        const callbacks = [...due.values()]
        due.clear()
        for (const callback of callbacks) callback(performance.now())
      })
    },
  }
}
