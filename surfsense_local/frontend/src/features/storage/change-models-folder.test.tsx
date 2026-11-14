import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ChangeModelsFolder } from "./change-models-folder"
import type { PlanResult, StorageBridge } from "./storage-types"

const FOLDER = {
  path: "/Users/ana/.surfsense",
  isDefault: true,
  connected: true,
  freeBytes: 64_300_000_000,
}

const READY: PlanResult = {
  status: "ready",
  kind: "models",
  source: "/Users/ana/.surfsense",
  target: "/Volumes/Big/SurfSense-Models",
  neededBytes: 1_100_000_000,
  freeBytes: 212_000_000_000,
  adopt: false,
}

function stubBridge(overrides: Partial<StorageBridge> = {}, models = FOLDER) {
  const bridge = {
    state: async () => ({ data: FOLDER, models }),
    choose: vi.fn(async () => READY),
    start: vi.fn(async () => true),
    ...overrides,
  } as unknown as StorageBridge
  window.surfsense = { ...window.surfsense!, storage: bridge }
  return bridge
}

afterEach(() => {
  cleanup()
  delete window.surfsense
})

async function openDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    await screen.findByRole("button", { name: "Change download folder" })
  )
}

describe("ChangeModelsFolder", () => {
  it("shows no folder until asked: the model step stays uncluttered", async () => {
    stubBridge()
    render(<ChangeModelsFolder />)

    await screen.findByRole("button", { name: "Change download folder" })
    expect(screen.queryByText(FOLDER.path)).toBeNull()
  })

  it("shows the current folder and its free space before any picker opens", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<ChangeModelsFolder />)

    await openDialog(user)

    expect(await screen.findByText(FOLDER.path)).toBeTruthy()
    expect(screen.getByText("64.3 GB free on this drive")).toBeTruthy()
    expect(bridge.choose).not.toHaveBeenCalled()
  })

  it("after a folder is chosen shows where the models move from and to", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<ChangeModelsFolder />)

    await openDialog(user)
    await user.click(
      await screen.findByRole("button", { name: "Choose folder…" })
    )

    expect(await screen.findByText("Move your models?")).toBeTruthy()
    expect(
      screen.getByText(READY.status === "ready" ? READY.source : "")
    ).toBeTruthy()
    expect(screen.getByText("/Volumes/Big/SurfSense-Models")).toBeTruthy()
    expect(screen.getByText("Needs 1.1 GB212 GB free")).toBeTruthy()
    expect(
      screen.getByText(/The old copy is removed automatically/)
    ).toBeTruthy()
    expect(bridge.start).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Move and restart" }))
    await waitFor(() => expect(bridge.start).toHaveBeenCalledOnce())
  })

  it("stays on the current folder when the picker is cancelled", async () => {
    stubBridge({ choose: vi.fn(async () => ({ status: "canceled" as const })) })
    const user = userEvent.setup()
    render(<ChangeModelsFolder />)

    await openDialog(user)
    await user.click(
      await screen.findByRole("button", { name: "Choose folder…" })
    )

    expect(await screen.findByText(FOLDER.path)).toBeTruthy()
    expect(screen.queryByText("Move your models?")).toBeNull()
  })

  it("cancelling the move starts nothing and closes the dialog", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<ChangeModelsFolder />)

    await openDialog(user)
    await user.click(
      await screen.findByRole("button", { name: "Choose folder…" })
    )
    await user.click(await screen.findByRole("button", { name: "Cancel" }))

    expect(bridge.start).not.toHaveBeenCalled()
    await waitFor(() =>
      expect(screen.queryByText("Move your models?")).toBeNull()
    )
  })

  it("is absent while the models drive is away", async () => {
    stubBridge({}, { ...FOLDER, connected: false })
    const { container } = render(<ChangeModelsFolder />)

    await waitFor(() => expect(container.textContent).toBe(""))
  })
})

describe("ChangeModelsFolder in the Docker image", { tags: ["docker"] }, () => {
  it("is absent: the volume decides where the files are", () => {
    const { container } = render(<ChangeModelsFolder />)
    expect(container.textContent).toBe("")
  })
})
