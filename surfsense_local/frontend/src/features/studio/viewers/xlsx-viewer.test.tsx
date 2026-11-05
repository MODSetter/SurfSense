import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { ArtifactDetail } from "../api"
import { XlsxViewer } from "./xlsx-viewer"

const renderer = vi.hoisted(() => ({
  construct: vi.fn(),
  load: vi.fn(),
  destroy: vi.fn(),
}))
vi.mock("@silurus/ooxml/xlsx", () => ({
  XlsxViewer: class {
    constructor(...args: unknown[]) {
      renderer.construct(...args)
    }
    load = renderer.load
    destroy = renderer.destroy
  },
}))

function workbook(size = 1000): ArtifactDetail {
  return {
    id: 7,
    generation: 1,
    title: "Budget",
    files: [{ role: "primary", size_bytes: size }],
  } as unknown as ArtifactDetail
}

function serve(
  response: () => Response = () => new Response(new ArrayBuffer(4))
) {
  const fetchMock = vi.fn(async () => response())
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

beforeEach(() => {
  renderer.construct.mockReset()
  renderer.load.mockReset().mockResolvedValue(undefined)
  renderer.destroy.mockReset()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Excel viewer", () => {
  it("draws the workbook's bytes", async () => {
    serve()
    render(<XlsxViewer artifact={workbook()} />)
    await vi.waitFor(() => expect(renderer.load).toHaveBeenCalled())
    expect(renderer.load.mock.lastCall![0].byteLength).toBe(4)
  })

  it("opens no link and asks the web for no font on a workbook's behalf", async () => {
    serve()
    render(<XlsxViewer artifact={workbook()} />)
    await vi.waitFor(() => expect(renderer.construct).toHaveBeenCalled())
    const options = renderer.construct.mock.lastCall![1]
    expect(options.enableHyperlinks).toBe(false)
    expect(options.useGoogleFonts).toBe(false)
    expect(options.wasmUrl).toMatch(/^data:application\/wasm;base64,/)
  })

  it("refuses a workbook over the limit before fetching it, with nothing to retry", async () => {
    const fetchMock = serve()
    render(<XlsxViewer artifact={workbook(16 * 1024 * 1024)} />)
    expect(await screen.findByText(/too large to preview/)).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("says so when the workbook cannot be read, and tries again on request", async () => {
    serve()
    renderer.load.mockRejectedValueOnce(new Error("damaged"))
    render(<XlsxViewer artifact={workbook()} />)
    expect(await screen.findByText(/could not be opened/)).toBeTruthy()
    act(() => screen.getByRole("button", { name: "Try again" }).click())
    await vi.waitFor(() => expect(renderer.load).toHaveBeenCalledTimes(2))
    await vi.waitFor(() =>
      expect(screen.queryByText(/could not be opened/)).toBeNull()
    )
  })

  it("says so when the workbook cannot be fetched", async () => {
    serve(() => new Response("", { status: 500 }))
    render(<XlsxViewer artifact={workbook()} />)
    expect(await screen.findByText(/can’t be previewed here/)).toBeTruthy()
  })

  it("frees the renderer when closed", async () => {
    serve()
    const { unmount } = render(<XlsxViewer artifact={workbook()} />)
    await vi.waitFor(() => expect(renderer.load).toHaveBeenCalled())
    unmount()
    expect(renderer.destroy).toHaveBeenCalled()
  })
})
