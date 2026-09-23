import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ImageModelsSettings } from "./image-models-settings"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function serving(localImage: Record<string, unknown>) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/image/local") return Response.json(localImage)
    if (path === "/llm/selection/image_gen" && init?.method === "PUT") {
      return Response.json({
        model_type: "image_gen",
        ...JSON.parse(String(init.body)),
        updated_at: "2026-09-24T00:00:00Z",
      })
    }
    if (path === "/llm/selection/image_gen") {
      return Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") return Response.json([])
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

const model = (overrides: Record<string, unknown> = {}) => ({
  name: "sd-turbo",
  label: "SD Turbo",
  detail: "Fast drafts.",
  size_bytes: 2_000_000_000,
  installed: true,
  selected: false,
  ...overrides,
})

describe("image model settings", () => {
  it("keeps the chat layout where no local image runtime shipped", async () => {
    vi.stubGlobal(
      "fetch",
      serving({ provider: "sdcpp", offered: false, ready: false, models: [] })
    )
    const user = userEvent.setup()
    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)

    expect(await screen.findByText("No image model yet")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Add model" }))

    // The same page as chat: the section says why nothing runs here.
    expect(
      screen.getByRole("heading", { name: "Add an image model" })
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Connect" })).toBeTruthy()
    expect(
      await screen.findByText("Image models cannot run on this computer")
    ).toBeTruthy()
  })

  it("uses a downloaded image model through the local image runtime", async () => {
    const fetchMock = serving({
      provider: "sdcpp",
      offered: true,
      ready: true,
      models: [model()],
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)
    await user.click(
      await screen.findByRole("button", { name: "Use SD Turbo" })
    )

    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/image_gen" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        provider: "sdcpp",
        connection_id: null,
        name: "sd-turbo",
      })
    })
  })

  it("will not delete the image model the runtime is serving", async () => {
    vi.stubGlobal(
      "fetch",
      serving({
        provider: "sdcpp",
        offered: true,
        ready: false,
        models: [model({ selected: true })],
      })
    )
    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)

    expect(await screen.findByText("Starting…")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Delete SD Turbo" })).toBeNull()
  })
})
