/**
 * Print CSS that turns docx-preview's pages into the document's own pages.
 *
 * docx-preview draws each section as one page box sized to the paper, but it
 * does not paginate: a long section is one tall box. Printing it with the
 * paper size and margins moved to @page lets Chromium paginate the content
 * the way a reader would see it, with margins on every page.
 */
export function printLayout(firstPage: HTMLElement | null): string {
  const page = firstPage?.style
  const size =
    page?.width && page.minHeight
      ? `size: ${page.width} ${page.minHeight};`
      : ""
  const margin = page?.paddingTop
    ? `margin: ${page.paddingTop} ${page.paddingRight} ${page.paddingBottom} ${page.paddingLeft};`
    : ""
  return `
@page { ${size} ${margin} }
html, body { margin: 0; padding: 0; background: white; }
section.docx {
  width: auto !important;
  min-height: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
  display: block !important;
  overflow: visible !important;
  box-shadow: none !important;
  break-after: page;
}
section.docx:last-of-type { break-after: auto; }
`
}
