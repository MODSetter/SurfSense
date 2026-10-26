import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { DataFolder } from "./data-folder"

const FOLDER = "C:\\Users\\ana\\.surfsense"

function stubBridge(openResult = "") {
  const openDataFolder = vi.fn(async () => openResult)
  window.surfsense = {
    ...window.surfsense!,
    about: {
      details: vi.fn(),
      dataFolder: async () => FOLDER,
      openDataFolder,
    },
  }
  return { openDataFolder }
}

afterEach(() => {
  cleanup()
  delete window.surfsense
  vi.restoreAllMocks()
})

describe("DataFolder", () => {
  it("names the folder that holds models, workspaces and settings", async () => {
    stubBridge()
    render(<DataFolder />)

    expect(await screen.findByText(FOLDER)).toBeTruthy()
  })

  it("opens that folder in the file manager", async () => {
    const { openDataFolder } = stubBridge()
    const user = userEvent.setup()
    render(<DataFolder />)

    await user.click(await screen.findByRole("button", { name: "Open folder" }))

    expect(openDataFolder).toHaveBeenCalledOnce()
  })

  it("shows nothing outside the desktop app", () => {
    render(<DataFolder />)

    expect(screen.queryByRole("button", { name: "Open folder" })).toBeNull()
  })
})
