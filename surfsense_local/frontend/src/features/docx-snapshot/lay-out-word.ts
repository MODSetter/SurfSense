import { renderAsync } from "docx-preview"

import { printLayout } from "./print-layout"

/** Lay a Word file out in `page` with the in-app viewer's library and set the
 *  print CSS that pages it as the document's own pages. */
export async function layOutWord(file: ArrayBuffer, page: Document) {
  // The in-app viewer's library and defaults, so the agent sees what the
  // user sees. Headers and footers are left out: docx-preview places them
  // in its page box, which print pagination replaces. Data URLs rather than
  // object URLs: the window is thrown away after printing, and the page then
  // also runs under jsdom, which has no URL.createObjectURL. No altChunks:
  // docx-preview puts their HTML in an unsandboxed iframe, where a script
  // the document carries would run as this page.
  await renderAsync(file, page.body, page.head, {
    inWrapper: false,
    renderHeaders: false,
    renderFooters: false,
    renderAltChunks: false,
    useBase64URL: true,
  })

  const style = page.createElement("style")
  style.textContent = printLayout(
    page.body.querySelector<HTMLElement>("section.docx")
  )
  page.head.append(style)
}
