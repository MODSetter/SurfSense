import { renderAsync } from "docx-preview"

import { printLayout } from "./print-layout"

/**
 * Lay out the Word file named by `?file=` for Electron to print to PDF.
 *
 * Resolves to null once the pages, their images and fonts are in place, or to
 * the reason it could not, in English for the agent: Electron cannot read a
 * rejected promise's message from a page.
 */
export async function layOutSnapshot(
  search: string,
  page: Document
): Promise<string | null> {
  const fileUrl = new URLSearchParams(search).get("file")
  if (!fileUrl) return "the snapshot page was opened without a file to lay out"

  let response: Response
  try {
    response = await fetch(fileUrl)
  } catch (error) {
    return `the Word file could not be fetched: ${messageOf(error)}`
  }
  if (!response.ok) {
    return `the Word file could not be fetched (HTTP ${response.status})`
  }
  try {
    // The in-app viewer's library and defaults, so the agent sees what the
    // user sees. Headers and footers are left out: docx-preview places them
    // in its page box, which print pagination replaces. Data URLs rather than
    // object URLs: the window is thrown away after printing, and the page then
    // also runs under jsdom, which has no URL.createObjectURL. No altChunks:
    // docx-preview puts their HTML in an unsandboxed iframe, where a script
    // the document carries would run as this page.
    await renderAsync(await response.arrayBuffer(), page.body, page.head, {
      inWrapper: false,
      renderHeaders: false,
      renderFooters: false,
      renderAltChunks: false,
      useBase64URL: true,
    })
  } catch (error) {
    return `the Word file could not be laid out: ${messageOf(error)}`
  }

  const style = page.createElement("style")
  style.textContent = printLayout(
    page.body.querySelector<HTMLElement>("section.docx")
  )
  page.head.append(style)

  await Promise.all([...page.images].map(loaded))
  await page.fonts?.ready
  return null
}

/** Settles once the image has loaded or failed; a broken image still prints. */
function loaded(image: HTMLImageElement): Promise<void> {
  if (image.complete) return Promise.resolve()
  return new Promise((resolve) => {
    image.addEventListener("load", () => resolve(), { once: true })
    image.addEventListener("error", () => resolve(), { once: true })
  })
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
