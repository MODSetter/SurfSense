import type { SnapshotFormat } from "./serve-snapshots.ts"

/** How printToPDF prints `pages` of a laid-out snapshot page of `format`. */
export function printOptions(
  format: SnapshotFormat,
  pages: string,
): Electron.PrintToPDFOptions {
  // The page sets @page: a Word file's own paper size and margins, or a deck's slide size.
  const options: Electron.PrintToPDFOptions = {
    preferCSSPageSize: true,
    printBackground: true,
    pageRanges: pages,
  }
  // Printed edge to edge, as a slide has no margin; Electron's default is 1 cm.
  if (format === "pptx") options.margins = { top: 0, bottom: 0, left: 0, right: 0 }
  return options
}
