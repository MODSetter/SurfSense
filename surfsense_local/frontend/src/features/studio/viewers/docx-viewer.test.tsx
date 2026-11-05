import { act, cleanup, render, screen } from "@testing-library/react"
import { strFromU8, unzipSync } from "fflate"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  textWatermark,
  WORD_TEXT_SHAPE_TYPE,
  wordFileWithHeader,
} from "@/features/word-document/watermarks/fixtures"
import type { ArtifactDetail } from "../api"
import { DocxViewer } from "./docx-viewer"

// The renderer draws to canvases jsdom cannot paint; its real output is checked
// in word-document/watermarks. Here is what the viewer asks of it.
const renderer = vi.hoisted(() => ({
  load: vi.fn(),
  fromDocument: vi.fn(),
}))
vi.mock("@silurus/ooxml/docx", () => ({
  DocxDocument: { load: renderer.load },
  DocxScrollViewer: { fromDocument: renderer.fromDocument },
}))
vi.mock("@silurus/ooxml/math", () => ({ math: { name: "math" } }))

function wordArtifact(id = 12, size = 1000): ArtifactDetail {
  return {
    id,
    generation: 1,
    title: "Client proposal",
    files: [{ role: "primary", size_bytes: size }],
  } as unknown as ArtifactDetail
}

function serve(file: ArrayBuffer = wordFileWithHeader("")) {
  const fetchMock = vi.fn(async () => new Response(file))
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function fakeDocument() {
  return { destroy: vi.fn(), getBookmarkPage: vi.fn() }
}

function fakeViewer() {
  return {
    destroy: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    scrollToPage: vi.fn(),
  }
}

async function open(artifact = wordArtifact()) {
  const actions = document.createElement("div")
  const view = render(
    <DocxViewer artifact={artifact} actionsContainer={actions} />
  )
  await vi.waitFor(() => expect(renderer.fromDocument).toHaveBeenCalled())
  return { ...view, actions }
}

/** What the viewer told the renderer to do on a link or a page. */
function viewerOptions() {
  return renderer.fromDocument.mock.lastCall![2]
}

beforeEach(() => {
  renderer.load.mockReset().mockImplementation(async () => fakeDocument())
  renderer.fromDocument.mockReset().mockImplementation(() => fakeViewer())
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Word viewer", () => {
  it("shows tracked changes and comments, as a revised copy is reviewed by them", async () => {
    serve()
    await open()
    expect(renderer.load.mock.lastCall![1].showTrackedChanges).toBe(true)
    expect(viewerOptions().comments).toBe(true)
  })

  it("draws equations and lets the reader select text", async () => {
    serve()
    await open()
    expect(renderer.load.mock.lastCall![1].math).toBeTruthy()
    expect(viewerOptions().enableTextSelection).toBe(true)
  })

  it("asks the web for no font on a document's behalf", async () => {
    serve()
    await open()
    expect(renderer.load.mock.lastCall![1].useGoogleFonts).toBe(false)
  })

  it("carries its parser inline, as the packaged app cannot fetch it from disk", async () => {
    serve()
    await open()
    expect(renderer.load.mock.lastCall![1].wasmUrl).toMatch(
      /^data:application\/wasm;base64,/
    )
  })

  it("gives the renderer the file's watermark in the form it draws", async () => {
    serve(wordFileWithHeader(WORD_TEXT_SHAPE_TYPE + textWatermark()))
    await open()
    const given = renderer.load.mock.lastCall![0] as ArrayBuffer
    const header = strFromU8(
      unzipSync(new Uint8Array(given))["word/header1.xml"]
    )
    expect(header).toContain("font-size:96pt")
  })

  it("opens no web page a document links to", async () => {
    serve()
    const opened = vi.fn()
    vi.stubGlobal("open", opened)
    await open()
    viewerOptions().onHyperlinkClick({
      kind: "external",
      url: "https://example.invalid/",
    })
    expect(opened).not.toHaveBeenCalled()
  })

  it("follows a link to a place in the document", async () => {
    serve()
    const document = fakeDocument()
    document.getBookmarkPage.mockReturnValue(3)
    const viewer = fakeViewer()
    renderer.load.mockResolvedValue(document)
    renderer.fromDocument.mockReturnValue(viewer)
    await open()
    viewerOptions().onHyperlinkClick({ kind: "internal", ref: "chapter-2" })
    expect(document.getBookmarkPage).toHaveBeenCalledWith("chapter-2")
    expect(viewer.scrollToPage).toHaveBeenCalledWith(3)
  })

  it("stays put on a link to a place that does not exist", async () => {
    serve()
    const viewer = fakeViewer()
    renderer.fromDocument.mockReturnValue(viewer)
    await open()
    viewerOptions().onHyperlinkClick({ kind: "internal", ref: "gone" })
    expect(viewer.scrollToPage).not.toHaveBeenCalled()
  })

  it("zooms from the panel's buttons", async () => {
    serve()
    const viewer = fakeViewer()
    renderer.fromDocument.mockReturnValue(viewer)
    const { actions } = await open()
    await vi.waitFor(() =>
      expect(actions.querySelector("button")).not.toBeNull()
    )
    const [zoomOut, zoomIn] = actions.querySelectorAll("button")
    act(() => zoomIn.click())
    act(() => zoomOut.click())
    expect(viewer.zoomIn).toHaveBeenCalledOnce()
    expect(viewer.zoomOut).toHaveBeenCalledOnce()
  })

  it("refuses a file over the limit before fetching it", async () => {
    const fetchMock = serve()
    render(
      <DocxViewer
        artifact={wordArtifact(12, 16 * 1024 * 1024)}
        actionsContainer={null}
      />
    )
    expect(await screen.findByText(/too large to preview/)).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("says so when the file cannot be read, and tries again on request", async () => {
    serve()
    renderer.load.mockRejectedValueOnce(new Error("not a Word file"))
    render(<DocxViewer artifact={wordArtifact()} actionsContainer={null} />)
    expect(await screen.findByText("not a Word file")).toBeTruthy()
    act(() => screen.getByRole("button", { name: "Try again" }).click())
    await vi.waitFor(() => expect(renderer.fromDocument).toHaveBeenCalled())
    expect(screen.queryByText("not a Word file")).toBeNull()
  })

  it("shows the version picked last when an earlier one finishes after it", async () => {
    serve()
    let finishFirst = (_: unknown) => {}
    const first = fakeDocument()
    renderer.load
      .mockImplementationOnce(
        () => new Promise((resolve) => (finishFirst = resolve))
      )
      .mockImplementation(async () => fakeDocument())
    const { rerender } = render(
      <DocxViewer artifact={wordArtifact(12)} actionsContainer={null} />
    )
    await vi.waitFor(() => expect(renderer.load).toHaveBeenCalledOnce())
    rerender(<DocxViewer artifact={wordArtifact(13)} actionsContainer={null} />)
    await vi.waitFor(() => expect(renderer.fromDocument).toHaveBeenCalledOnce())

    await act(async () => finishFirst(first))

    expect(first.destroy).toHaveBeenCalled()
    expect(renderer.fromDocument).toHaveBeenCalledOnce()
  })

  it("frees the document and its viewer when closed", async () => {
    serve()
    const document = fakeDocument()
    const viewer = fakeViewer()
    renderer.load.mockResolvedValue(document)
    renderer.fromDocument.mockReturnValue(viewer)
    const { unmount } = await open()
    await vi.waitFor(() => expect(renderer.fromDocument).toHaveBeenCalled())
    unmount()
    expect(viewer.destroy).toHaveBeenCalled()
    expect(document.destroy).toHaveBeenCalled()
  })
})
