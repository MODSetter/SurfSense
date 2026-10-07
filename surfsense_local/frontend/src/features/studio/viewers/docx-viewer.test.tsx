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

import { CLAUSE_WITH_TRACKED_CHANGES } from "@/features/docx-snapshot/fixtures/clause-with-tracked-changes"
import { CLAUSES_WITH_COMMENTS } from "@/features/docx-snapshot/fixtures/clauses-with-comments"
import { LINKS_OF_EVERY_KIND } from "@/features/docx-snapshot/fixtures/links-of-every-kind"
import { REPORT_WITH_ALT_CHUNK } from "@/features/docx-snapshot/fixtures/report-with-alt-chunk"
import { STYLES_THAT_LOAD_REMOTE_IMAGES } from "@/features/docx-snapshot/fixtures/styles-that-load-remote-images"
import type { ArtifactDetail } from "../api"
import { COMMENT_GUTTER } from "./docx-comments"
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
    refinable: false,
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

/**
 * The zoom the viewer fits a Word file at: jsdom lays nothing out, so this is
 * a 600 px frame whose scrollbar leaves 585 px, holding pages 816 px wide.
 */
async function fitZoom(file: Uint8Array<ArrayBuffer>): Promise<string> {
  serve({ 12: file })
  const { container } = render(
    <DocxViewer artifact={wordArtifact(12, file)} actionsContainer={null} />
  )
  const frame = container.querySelector("iframe")!
  Object.defineProperty(frame, "clientWidth", { value: 600 })
  const pages = pagesOf(container)
  Object.defineProperty(pages.documentElement, "clientWidth", { value: 585 })
  // docx-preview may make the page in either window's realm.
  const frameWindow = pages.defaultView as unknown as typeof globalThis
  const realms = [HTMLElement.prototype, frameWindow.HTMLElement.prototype]
  const own = realms.map((prototype) =>
    Object.getOwnPropertyDescriptor(prototype, "offsetWidth")
  )
  for (const prototype of realms) {
    Object.defineProperty(prototype, "offsetWidth", {
      configurable: true,
      get(this: HTMLElement) {
        return this.classList.contains("docx") ? 816 : 0
      },
    })
  }

  try {
    await vi.waitFor(() =>
      expect(pages.body.style.getPropertyValue("zoom")).not.toMatch(/^1?$/)
    )
    return pages.body.style.getPropertyValue("zoom")
  } finally {
    realms.forEach((prototype, index) => {
      const descriptor = own[index]
      if (descriptor)
        Object.defineProperty(prototype, "offsetWidth", descriptor)
      else Reflect.deleteProperty(prototype, "offsetWidth")
    })
  }
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

  it("shows tracked changes: insertions underlined, deletions struck through", async () => {
    const pages = await open(CLAUSE_WITH_TRACKED_CHANGES)

    const inserted = pages.querySelector("ins")
    const deleted = pages.querySelector("del")
    expect(inserted?.textContent).toBe("45")
    expect(deleted?.textContent).toBe("30")
    const view = pages.defaultView!
    expect(view.getComputedStyle(inserted!).textDecorationLine).toContain(
      "underline"
    )
    expect(view.getComputedStyle(deleted!).textDecorationLine).toContain(
      "line-through"
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

  it("fits the page to the frame's viewport, leaving out its scrollbar", async () => {
    expect(await fitZoom(LINKS_OF_EVERY_KIND)).toBe(String(585 / 816))
  })

  it("fits the comments' balloons beside the page", async () => {
    expect(await fitZoom(CLAUSES_WITH_COMMENTS)).toBe(
      String(585 / (816 + COMMENT_GUTTER))
    )
  })

  it("shows each comment numbered in a balloon, its passage shaded", async () => {
    const pages = await open(CLAUSES_WITH_COMMENTS)

    const balloons = [...pages.querySelectorAll(".surfsense-comment")]
    expect(balloons.map((balloon) => balloon.textContent)).toEqual([
      expect.stringMatching(
        /^1SurfSense.*2026.*Cash flow: the request asks for payment within 30 days\.$/
      ),
      // Saved without a date, so it shows none rather than 1970.
      "2SurfSenseTermination should be mutual.",
    ])
    const refs = [...pages.querySelectorAll(".surfsense-comment-ref")]
    expect(refs.map((ref) => ref.textContent)).toEqual(["1", "2"])
    const shaded = (note: string) =>
      [
        ...pages.querySelectorAll(
          `.surfsense-comment-anchor[data-note="${note}"]`
        ),
      ]
        .map((shade) => shade.textContent)
        .join("")
    // The first comment covers the change: "60" struck through, "30" put in.
    expect(shaded("1")).toBe("6030")
    expect(shaded("2")).toBe("terminate on notice")
    // Not hidden behind a hover, as docx-preview leaves them.
    expect(pages.querySelector(".docx-comment-popover")).toBeNull()
    expect(pages.body.textContent).not.toContain("💬")
  })

  it("keeps the balloons in the margin beside the pages", async () => {
    const pages = await open(CLAUSES_WITH_COMMENTS)

    const wrapper = pages.querySelector<HTMLElement>(".docx-wrapper")!
    expect(wrapper.style.paddingRight).toBe(`${30 + COMMENT_GUTTER}px`)
    const balloon = pages.querySelector<HTMLElement>(".surfsense-comment")!
    expect(balloon.parentElement).toBe(wrapper)
    // From the middle, as the pages are centred: jsdom gives them no width.
    expect(balloon.style.left).toMatch(/^calc\(50% [+-] \d+px\)$/)
    expect(balloon.style.top).toMatch(/px$/)
    // A link in a comment is disarmed as one in the text is.
    expect(pages.querySelector('a[href]:not([href^="#"])')).toBeNull()
  })

  it("leaves a file without comments as it was, with no margin", async () => {
    const pages = await open(CLAUSE_WITH_TRACKED_CHANGES)

    expect(pages.querySelector(".surfsense-comment")).toBeNull()
    expect(
      pages.querySelector<HTMLElement>(".docx-wrapper")!.style.paddingRight
    ).toBe("")
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
