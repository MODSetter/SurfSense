import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { StorageSettings } from "./storage-settings"
import type { PlanResult, StorageBridge, StorageState } from "./storage-types"

const MOVED_NOTHING: StorageState = {
  data: {
    path: "C:\\Users\\ana\\.surfsense",
    isDefault: true,
    connected: true,
    freeBytes: 38_000_000_000,
  },
  models: {
    path: "C:\\Users\\ana\\.surfsense",
    isDefault: true,
    connected: true,
    freeBytes: 38_000_000_000,
  },
}

const READY: PlanResult = {
  status: "ready",
  kind: "models",
  source: "C:\\Users\\ana\\.surfsense",
  target: "D:\\SurfSense-Models",
  neededBytes: 12_000_000_000,
  freeBytes: 212_000_000_000,
  adopt: false,
}

function stubBridge(
  overrides: Partial<StorageBridge> = {},
  state = MOVED_NOTHING
) {
  const bridge: StorageBridge = {
    state: async () => state,
    choose: vi.fn(async () => READY),
    planDefault: vi.fn(async () => READY),
    start: vi.fn(async () => true),
    cancel: vi.fn(async () => undefined),
    restart: vi.fn(async () => undefined),
    onProgress: () => () => undefined,
    ...overrides,
  }
  window.surfsense = { ...window.surfsense!, storage: bridge }
  return bridge
}

afterEach(() => {
  cleanup()
  delete window.surfsense
  vi.restoreAllMocks()
})

describe("StorageSettings", () => {
  it("shows where models and data are, and how much room each drive has", async () => {
    stubBridge(
      {},
      {
        ...MOVED_NOTHING,
        models: {
          path: "D:\\SurfSense-Models",
          isDefault: false,
          connected: true,
          freeBytes: 212_000_000_000,
        },
      }
    )
    render(<StorageSettings />)

    expect(await screen.findByText("D:\\SurfSense-Models")).toBeTruthy()
    expect(screen.getByText("C:\\Users\\ana\\.surfsense")).toBeTruthy()
    expect(screen.getByText("212 GB free on this drive")).toBeTruthy()
  })

  it("moves nothing until the user confirms what the move will cost", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<StorageSettings />)

    const [changeModels] = await screen.findAllByRole("button", {
      name: "Change…",
    })
    await user.click(changeModels!)

    expect(await screen.findByText("Move your models?")).toBeTruthy()
    expect(screen.getByText("D:\\SurfSense-Models")).toBeTruthy()
    expect(screen.getByText("Needs 12 GB212 GB free")).toBeTruthy()
    expect(screen.getByText("From")).toBeTruthy()
    expect(bridge.choose).toHaveBeenCalledWith("models")
    expect(bridge.start).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Move and restart" }))
    await waitFor(() => expect(bridge.start).toHaveBeenCalledOnce())
  })

  it("starts no move when the user cancels the confirmation", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<StorageSettings />)

    const [changeModels] = await screen.findAllByRole("button", {
      name: "Change…",
    })
    await user.click(changeModels!)
    await user.click(await screen.findByRole("button", { name: "Cancel" }))

    expect(bridge.start).not.toHaveBeenCalled()
  })

  it("warns that a moved data folder is needed for SurfSense to start", async () => {
    stubBridge({
      choose: vi.fn(async () => ({ ...READY, kind: "data" as const })),
    })
    const user = userEvent.setup()
    render(<StorageSettings />)

    const buttons = await screen.findAllByRole("button", { name: "Change…" })
    await user.click(buttons[1]!)

    expect(
      await screen.findByText(/won’t start unless this drive is connected/)
    ).toBeTruthy()
  })

  it("says the old copy goes by itself, so nobody looks for it to delete", async () => {
    stubBridge()
    const user = userEvent.setup()
    render(<StorageSettings />)

    const [changeModels] = await screen.findAllByRole("button", {
      name: "Change…",
    })
    await user.click(changeModels!)

    expect(
      await screen.findByText(/The old copy is removed automatically/)
    ).toBeTruthy()
  })

  it("says it will switch, not copy, to a folder that already holds models", async () => {
    stubBridge({
      choose: vi.fn(async () => ({ ...READY, adopt: true, neededBytes: 0 })),
    })
    const user = userEvent.setup()
    render(<StorageSettings />)

    const [changeModels] = await screen.findAllByRole("button", {
      name: "Change…",
    })
    await user.click(changeModels!)

    expect(
      await screen.findByRole("button", { name: "Switch and restart" })
    ).toBeTruthy()
    expect(screen.queryByText("From")).toBeNull()
  })

  it("offers the way back only once a folder has moved", async () => {
    stubBridge(
      {},
      {
        ...MOVED_NOTHING,
        models: {
          path: "D:\\SurfSense-Models",
          isDefault: false,
          connected: true,
          freeBytes: 1,
        },
      }
    )
    render(<StorageSettings />)

    expect(
      await screen.findAllByRole("button", { name: "Move back to default" })
    ).toHaveLength(1)
  })

  it("does not offer a move while the models drive is away", async () => {
    stubBridge(
      {},
      {
        ...MOVED_NOTHING,
        models: {
          path: "E:\\SurfSense-Models",
          isDefault: false,
          connected: false,
          freeBytes: null,
        },
      }
    )
    render(<StorageSettings />)

    expect(await screen.findByText("This drive isn’t connected.")).toBeTruthy()
    const [changeModels, changeData] = screen.getAllByRole("button", {
      name: "Change…",
    })
    expect((changeModels as HTMLButtonElement).disabled).toBe(true)
    expect((changeData as HTMLButtonElement).disabled).toBe(false)
  })
})
