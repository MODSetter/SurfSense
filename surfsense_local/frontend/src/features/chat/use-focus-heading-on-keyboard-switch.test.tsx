import { afterEach, describe, expect, it } from "vitest"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { useRef } from "react"

import { useFocusHeadingOnKeyboardSwitch } from "./use-focus-heading-on-keyboard-switch"

afterEach(cleanup)

function Conversation({ threadId }: { threadId: number | null }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useFocusHeadingOnKeyboardSwitch(threadId, heading)
  return (
    <>
      <h2 ref={heading} tabIndex={-1}>
        Thread
      </h2>
      <div data-composer-placement="bottom">
        <input aria-label="Message" />
      </div>
    </>
  )
}

/** Lets the hook's queued focus run. */
const settle = () =>
  act(() => new Promise((resolve) => setTimeout(resolve, 10)))

describe("useFocusHeadingOnKeyboardSwitch", () => {
  it("focuses the heading after a switch made from the keyboard", async () => {
    const { rerender } = render(<Conversation threadId={1} />)

    fireEvent.keyDown(document.body, { key: "Enter" })
    rerender(<Conversation threadId={2} />)
    await settle()

    expect(document.activeElement).toBe(screen.getByRole("heading"))
  })

  it("leaves the composer focused when sending creates the thread", async () => {
    // A first message sent with Enter turns a new chat into a thread; that is
    // not a switch, and the person is still writing.
    const { rerender } = render(<Conversation threadId={null} />)
    const composer = screen.getByRole("textbox", { name: "Message" })
    composer.focus()

    fireEvent.keyDown(composer, { key: "Enter" })
    rerender(<Conversation threadId={2} />)
    await settle()

    expect(document.activeElement).toBe(composer)
  })

  it("leaves focus alone after a switch made with the pointer", async () => {
    const { rerender } = render(<Conversation threadId={1} />)
    const composer = screen.getByRole("textbox", { name: "Message" })
    composer.focus()

    fireEvent.pointerDown(document.body)
    rerender(<Conversation threadId={2} />)
    await settle()

    expect(document.activeElement).toBe(composer)
  })
})
