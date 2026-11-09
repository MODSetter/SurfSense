import { openWordDocument } from "@/features/word-document/open-word-document"

import { printedPages } from "./printed-pages"

// Sharp enough for the agent to read small print from a preview.
const PIXELS_PER_POINT = 2

/** Lay a Word file out in `page`, one image per page at the document's own page
 *  size, for printing: the viewer's renderer, so the agent sees what the user
 *  sees, headers, watermarks and tracked changes included. Only the pages in
 *  `ranges` are drawn; each other one is a blank of its size, so the printed
 *  pages keep their numbers. */
export async function layOutWord(
  file: ArrayBuffer,
  page: Document,
  ranges: string | null = null
) {
  const printed = printedPages(ranges)
  const document = await openWordDocument(file)
  try {
    await document.waitUntilLayoutComplete()
    const rules: string[] = [
      "html, body { margin: 0; padding: 0; background: white; }",
      ".word-page { display: block; break-after: page; }",
      ".word-page:last-child { break-after: auto; }",
    ]
    for (let index = 0; index < document.pageCount; index++) {
      const { widthPt, heightPt } = document.pageSize(index)
      const sheet = printed(index)
        ? await drawnPage(document, index, widthPt, page)
        : page.createElement("div")
      sheet.className = "word-page"
      const name = `word-page-${index}`
      sheet.style.width = `${widthPt}pt`
      sheet.style.height = `${heightPt}pt`
      sheet.style.setProperty("page", name)
      rules.push(
        `@page ${name} { size: ${widthPt}pt ${heightPt}pt; margin: 0 }`
      )
      page.body.append(sheet)
    }
    const style = page.createElement("style")
    style.textContent = rules.join("\n")
    page.head.append(style)
  } finally {
    document.destroy()
  }
}

async function drawnPage(
  document: Awaited<ReturnType<typeof openWordDocument>>,
  index: number,
  widthPt: number,
  page: Document
): Promise<HTMLImageElement> {
  const canvas = page.createElement("canvas")
  await document.renderPage(canvas, index, {
    width: widthPt,
    dpr: PIXELS_PER_POINT,
  })
  // An image, not the canvas: a long file's pages would otherwise all stay
  // decoded in memory until the print.
  const image = page.createElement("img")
  image.src = await imageOf(canvas)
  return image
}

function imageOf(canvas: HTMLCanvasElement): Promise<string> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(URL.createObjectURL(blob))
      else reject(new Error("a page could not be drawn"))
    }, "image/png")
  })
}
