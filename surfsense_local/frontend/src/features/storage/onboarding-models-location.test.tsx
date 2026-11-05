import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { OnboardingModelsLocation } from "./onboarding-models-location"
import type { StorageBridge } from "./storage-types"

const FOLDER = { path: "/Users/ana/.surfsense", isDefault: true, connected: true, freeBytes: 18_000_000_000 }

function stubBridge() {
  const bridge = {
    state: async () => ({ data: FOLDER, models: FOLDER }),
    choose: vi.fn(async () => ({ status: "canceled" as const })),
  } as unknown as StorageBridge
  window.surfsense = { ...window.surfsense!, storage: bridge }
  return bridge
}

afterEach(() => {
  cleanup()
  delete window.surfsense
})

describe("OnboardingModelsLocation", () => {
  it("names the folder and its free space, and lets the user change it", async () => {
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<OnboardingModelsLocation />)

    expect(await screen.findByText("Models save to /Users/ana/.surfsense · 18 GB free")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Change" }))
    expect(bridge.choose).toHaveBeenCalledWith("models")
  })

  it("stands out when the chosen model will not fit", async () => {
    stubBridge()
    render(<OnboardingModelsLocation neededBytes={20_000_000_000} />)

    const line = await screen.findByText(/18 GB free/)
    expect(line.className).toContain("text-destructive")
  })

  it("stays quiet when it fits", async () => {
    stubBridge()
    render(<OnboardingModelsLocation neededBytes={4_000_000_000} />)

    const line = await screen.findByText(/18 GB free/)
    expect(line.className).not.toContain("text-destructive")
  })
})

describe("OnboardingModelsLocation in the Docker image", { tags: ["docker"] }, () => {
  it("is absent: the volume decides where the files are", () => {
    const { container } = render(<OnboardingModelsLocation />)
    expect(container.textContent).toBe("")
  })
})
