import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ResizeHandle } from "./resize-handle"

afterEach(cleanup)

/** A column that keeps what its edge reports, as the dashboard does. */
function Column({
  side = "start",
  initial = 300,
  min = 272,
  max = 560,
  onCommitted = vi.fn(),
  onReset = vi.fn(),
  onDraggingChange = vi.fn(),
}: {
  side?: "start" | "end"
  initial?: number
  min?: number
  max?: number
  onCommitted?: (value: number) => void
  onReset?: () => void
  onDraggingChange?: (dragging: boolean) => void
}) {
  const [width, setWidth] = useState(initial)
  return (
    <ResizeHandle
      side={side}
      value={width}
      min={min}
      max={max}
      label="Resize sidebar"
      onValueChange={setWidth}
      onValueCommitted={(value) => {
        setWidth(value)
        onCommitted(value)
      }}
      onReset={onReset}
      onDraggingChange={onDraggingChange}
    />
  )
}

function handle() {
  return screen.getByRole("separator", { name: "Resize sidebar" })
}

function drag(element: HTMLElement, from: number, to: number) {
  fireEvent.pointerDown(element, { button: 0, pointerId: 1, clientX: from })
  fireEvent.pointerMove(element, { pointerId: 1, clientX: (from + to) / 2 })
  fireEvent.pointerMove(element, { pointerId: 1, clientX: to })
  fireEvent.pointerUp(element, { pointerId: 1, clientX: to })
}

describe("resize handle", () => {
  it("is a focusable vertical separator that states its width and range", () => {
    render(<Column />)

    const separator = handle()
    expect(separator.getAttribute("aria-orientation")).toBe("vertical")
    expect(separator.getAttribute("aria-valuenow")).toBe("300")
    expect(separator.getAttribute("aria-valuemin")).toBe("272")
    expect(separator.getAttribute("aria-valuemax")).toBe("560")
    expect(separator.tabIndex).toBe(0)
  })

  it("follows a drag and keeps the width once it is let go", () => {
    const onCommitted = vi.fn()
    const onDraggingChange = vi.fn()
    render(
      <Column onCommitted={onCommitted} onDraggingChange={onDraggingChange} />
    )

    fireEvent.pointerDown(handle(), { button: 0, pointerId: 1, clientX: 500 })
    expect(onDraggingChange).toHaveBeenLastCalledWith(true)
    expect(document.body.style.userSelect).toBe("none")
    fireEvent.pointerMove(handle(), { pointerId: 1, clientX: 540 })
    expect(handle().getAttribute("aria-valuenow")).toBe("340")
    // Nothing is kept until the drag ends.
    expect(onCommitted).not.toHaveBeenCalled()
    fireEvent.pointerUp(handle(), { pointerId: 1, clientX: 540 })

    expect(onCommitted).toHaveBeenCalledExactlyOnceWith(340)
    expect(onDraggingChange).toHaveBeenLastCalledWith(false)
    expect(document.body.style.userSelect).toBe("")
  })

  it("grows a column on the end side as its edge moves left", () => {
    const onCommitted = vi.fn()
    render(
      <Column side="end" initial={400} max={640} onCommitted={onCommitted} />
    )

    drag(handle(), 800, 720)

    expect(onCommitted).toHaveBeenCalledExactlyOnceWith(480)
  })

  it("stops a drag at the minimum and the maximum", () => {
    const onCommitted = vi.fn()
    render(<Column onCommitted={onCommitted} />)

    drag(handle(), 500, 100)
    expect(onCommitted).toHaveBeenLastCalledWith(272)
    drag(handle(), 500, 1200)
    expect(onCommitted).toHaveBeenLastCalledWith(560)
  })

  it("keeps nothing for a press that does not move", () => {
    const onCommitted = vi.fn()
    render(<Column onCommitted={onCommitted} />)

    drag(handle(), 500, 500)

    expect(onCommitted).not.toHaveBeenCalled()
  })

  it("steps with the arrow keys and jumps to either end with Home and End", async () => {
    const onCommitted = vi.fn()
    const user = userEvent.setup()
    render(<Column onCommitted={onCommitted} />)

    handle().focus()
    await user.keyboard("{ArrowRight}")
    expect(onCommitted).toHaveBeenLastCalledWith(316)
    await user.keyboard("{ArrowLeft}{ArrowLeft}")
    expect(onCommitted).toHaveBeenLastCalledWith(284)
    // Already within a step of the minimum: it stops there.
    await user.keyboard("{ArrowLeft}")
    expect(onCommitted).toHaveBeenLastCalledWith(272)
    await user.keyboard("{End}")
    expect(onCommitted).toHaveBeenLastCalledWith(560)
    await user.keyboard("{Home}")
    expect(onCommitted).toHaveBeenLastCalledWith(272)
    expect(handle().getAttribute("aria-valuenow")).toBe("272")
  })

  it("moves the edge, not the column, with the arrow keys on the end side", async () => {
    const onCommitted = vi.fn()
    const user = userEvent.setup()
    render(
      <Column side="end" initial={400} max={640} onCommitted={onCommitted} />
    )

    handle().focus()
    await user.keyboard("{ArrowLeft}")
    expect(onCommitted).toHaveBeenLastCalledWith(416)
  })

  it("asks for the default width on a double-click", async () => {
    const onReset = vi.fn()
    const user = userEvent.setup()
    render(<Column onReset={onReset} />)

    await user.dblClick(handle())

    expect(onReset).toHaveBeenCalledOnce()
  })
})
