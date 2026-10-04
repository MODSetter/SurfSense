import { cleanup, render } from "@testing-library/react"
import { renderAsync } from "docx-preview"
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest"

import { LINKS_OF_EVERY_KIND } from "@/features/docx-snapshot/fixtures/links-of-every-kind"
import { REPORT_WITH_ALT_CHUNK } from "@/features/docx-snapshot/fixtures/report-with-alt-chunk"
import { STYLES_THAT_LOAD_REMOTE_IMAGES } from "@/features/docx-snapshot/fixtures/styles-that-load-remote-images"
import type { ArtifactDetail } from "../api"
import { DocxViewer } from "./docx-viewer"

// The real library, watched so a test can hold one render back.
vi.mock("docx-preview", async (importOriginal) => {
  const real = await importOriginal<typeof import("docx-preview")>()
  return { ...real, renderAsync: vi.fn(real.renderAsync) }
})

function wordArtifact(
  id: number,
  file: Uint8Array<ArrayBuffer>
): ArtifactDetail {
  return {
    id,
    document_id: 40,
    format: "docx",
    generation: 1,
    title: "Client proposal",
    status: "ready",
    error_message: null,
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
    version: { root_id: 12, number: id - 11, parent_id: null },
    spec_kind: "python",
    content: null,
    files: [
      {
        role: "primary",
        mime_type:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes: file.byteLength,
        original_filename: "Client proposal.docx",
      },
    ],
    quiz_state: null,
    flashcard_state: null,
  }
}

/** Serves each artifact's Word file by the id in the URL. */
function serve(files: Record<number, Uint8Array<ArrayBuffer>>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const id = Number(/\/artifacts\/(\d+)\//.exec(url)?.[1])
      return new Response(files[id])
    })
  )
}

/** The document the viewer lays the Word file's pages out in. */
function pagesOf(viewer: HTMLElement): Document {
  const frame = viewer.querySelector("iframe")
  expect(frame?.contentDocument).toBeTruthy()
  return frame!.contentDocument!
}

async function open(file: Uint8Array<ArrayBuffer>): Promise<Document> {
  serve({ 12: file })
  const { container } = render(
    <DocxViewer artifact={wordArtifact(12, file)} actionsContainer={null} />
  )
  await vi.waitFor(() =>
    expect(pagesOf(container).querySelector("section.docx")).not.toBeNull()
  )
  return pagesOf(container)
}

function link(pages: Document, text: string): HTMLAnchorElement | null {
  const links = [...pages.querySelectorAll("a")]
  return links.find((anchor) => anchor.textContent === text) ?? null
}

function policyOf(pages: Document): Map<string, string[]> {
  const policy = pages
    .querySelector('head > meta[http-equiv="Content-Security-Policy"]')
    ?.getAttribute("content")
  return new Map(
    (policy ?? "")
      .split(";")
      .map((directive) => directive.trim().split(/\s+/))
      .filter(([name]) => name)
      .map(([name, ...sources]) => [name, sources])
  )
}

// docx-preview sizes a VML shape from its SVG box, which jsdom does not lay out.
beforeAll(() => {
  Object.defineProperty(SVGElement.prototype, "getBBox", {
    configurable: true,
    value: () => ({ x: 0, y: 0, width: 0, height: 0 }),
  })
})

afterAll(() => {
  Reflect.deleteProperty(SVGElement.prototype, "getBBox")
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.mocked(renderAsync).mockClear()
})

describe("Word viewer", () => {
  it("leaves out HTML the Word file carries, so none of its script runs", async () => {
    const pages = await open(REPORT_WITH_ALT_CHUNK)

    expect(pages.body.textContent).toContain("Quarterly report")
    expect(pages.querySelector("iframe")).toBeNull()
  })

  it("lays the pages out in a frame of their own that runs no script", async () => {
    const pages = await open(STYLES_THAT_LOAD_REMOTE_IMAGES)

    const frame = pages.defaultView?.frameElement
    expect(frame?.getAttribute("sandbox")).toBe("allow-same-origin")
    expect(pages.body.textContent).toContain("Proposal")
  })

  it("keeps the Word file's styles out of the app's own window", async () => {
    const pages = await open(STYLES_THAT_LOAD_REMOTE_IMAGES)

    const ownStyles = [...document.querySelectorAll("style")]
      .map((style) => style.textContent)
      .join("\n")
    const ownInlineStyles = [...document.querySelectorAll("[style]")]
      .map((element) => element.getAttribute("style"))
      .join("\n")
    expect(ownStyles).not.toContain("tracker.example")
    expect(ownInlineStyles).not.toContain("tracker.example")
    // The global rule the font name smuggles in lands in the frame instead.
    const frameStyles = [...pages.querySelectorAll("style")]
      .map((style) => style.textContent)
      .join("\n")
    expect(frameStyles).toContain("https://tracker.example/beacon")
  })

  it("lets the frame load images and fonts from the file alone, never the web", async () => {
    const pages = await open(STYLES_THAT_LOAD_REMOTE_IMAGES)

    const policy = policyOf(pages)
    expect(policy.get("default-src")).toEqual(["'none'"])
    expect(policy.get("style-src")).toEqual(["'unsafe-inline'"])
    expect(policy.get("img-src")).toEqual(["data:"])
    expect(policy.get("font-src")).toEqual(["data:"])
    // Set before the file's styles, so it already covers their first load.
    expect(pages.head.firstElementChild?.getAttribute("http-equiv")).toBe(
      "Content-Security-Policy"
    )
  })

  it("keeps no link that would run script when clicked", async () => {
    const pages = await open(LINKS_OF_EVERY_KIND)

    expect(link(pages, "Open the chart")?.hasAttribute("href")).toBe(false)
    expect(pages.querySelector('a[href^="javascript:" i]')).toBeNull()
  })

  it("follows no web link, since the app opens none of them", async () => {
    const pages = await open(LINKS_OF_EVERY_KIND)

    const website = link(pages, "Our website")
    expect(website).not.toBeNull()
    expect(website?.hasAttribute("href")).toBe(false)
    expect(website?.hasAttribute("target")).toBe(false)
  })

  it("keeps a link to a place in the document, within the document", async () => {
    const pages = await open(LINKS_OF_EVERY_KIND)

    const pricing = link(pages, "See pricing")
    expect(pricing?.getAttribute("href")).toBe("#pricing")
    // Not the app's own address with #pricing on it, which would load the
    // app into the frame instead of scrolling.
    expect(pricing?.href).toBe("about:blank#pricing")
  })

  it("shows the version picked last when an earlier one finishes after it", async () => {
    const { renderAsync: realRenderAsync } =
      await vi.importActual<typeof import("docx-preview")>("docx-preview")
    let releaseFirst = () => {}
    const firstHeld = new Promise<void>((resolve) => {
      releaseFirst = resolve
    })
    vi.mocked(renderAsync).mockImplementationOnce(async (...args) => {
      await firstHeld
      return realRenderAsync(...args)
    })
    serve({ 12: LINKS_OF_EVERY_KIND, 13: REPORT_WITH_ALT_CHUNK })

    const { container, rerender } = render(
      <DocxViewer
        artifact={wordArtifact(12, LINKS_OF_EVERY_KIND)}
        actionsContainer={null}
      />
    )
    await vi.waitFor(() => expect(renderAsync).toHaveBeenCalledTimes(1))
    rerender(
      <DocxViewer
        artifact={wordArtifact(13, REPORT_WITH_ALT_CHUNK)}
        actionsContainer={null}
      />
    )
    await vi.waitFor(() =>
      expect(pagesOf(container).body.textContent).toContain("Quarterly report")
    )
    releaseFirst()
    await vi.waitFor(() =>
      expect(vi.mocked(renderAsync).mock.settledResults[0]?.type).toBe(
        "fulfilled"
      )
    )

    const pages = pagesOf(container)
    expect(pages.body.textContent).toContain("Quarterly report")
    expect(pages.body.textContent).not.toContain("Open the chart")
    expect(pages.querySelector('a[href^="javascript:" i]')).toBeNull()
  })
})
