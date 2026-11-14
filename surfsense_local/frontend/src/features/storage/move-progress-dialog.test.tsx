import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { MoveProgressDialog } from "./move-progress-dialog"
import { followMoveProgress } from "./move-progress-state"
import type { MoveProgress, StorageBridge } from "./storage-types"

let push: (progress: MoveProgress) => void = () => undefined
let stopFollowing: () => void = () => undefined

function stubBridge() {
  const bridge = {
    cancel: vi.fn(async () => undefined),
    restart: vi.fn(async () => undefined),
    onProgress: (listener: (progress: MoveProgress) => void) => {
      push = listener
      return () => undefined
    },
  } as unknown as StorageBridge
  window.surfsense = { ...window.surfsense!, storage: bridge }
  stopFollowing = followMoveProgress()
  return bridge
}

afterEach(() => {
  act(() => stopFollowing())
  cleanup()
  delete window.surfsense
})

describe("MoveProgressDialog", () => {
  it("shows nothing until a move starts", () => {
    stubBridge()
    render(<MoveProgressDialog />)
    expect(screen.queryByText("Moving your files")).toBeNull()
  })

  it("covers the page as soon as the sidecars begin to stop", async () => {
    stubBridge()
    render(<MoveProgressDialog />)

    act(() => push({ phase: "stopping" }))

    expect(await screen.findByText("Moving your files")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull()
  })

  it("shows how far the copy has got, and can be cancelled", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<MoveProgressDialog />)

    act(() => push({ phase: "copying", doneBytes: 25, totalBytes: 100 }))

    expect(await screen.findByText("25%")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(bridge.cancel).toHaveBeenCalledOnce()
  })

  it("cannot be cancelled once it is switching: the change is one step", async () => {
    stubBridge()
    render(<MoveProgressDialog />)

    act(() => push({ phase: "switching", doneBytes: 100, totalBytes: 100 }))

    expect(await screen.findByText("Finishing up…")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull()
  })

  it("after a failure says nothing was lost and restarts on request", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<MoveProgressDialog />)

    act(() => push({ phase: "failed", reason: "no_room" }))

    expect(await screen.findByText("Your files weren’t moved")).toBeTruthy()
    expect(screen.getByText(/ran out of space.*Nothing was lost/)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Restart SurfSense" }))
    expect(bridge.restart).toHaveBeenCalledOnce()
  })
})
