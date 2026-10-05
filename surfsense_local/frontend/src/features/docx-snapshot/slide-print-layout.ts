/**
 * Print CSS that puts each slide on a page of the deck's own size, edge to
 * edge, so a printed page is what the slide shows.
 */
export function slidePrintLayout(width: number, height: number): string {
  return `
@page { size: ${width}px ${height}px; margin: 0; }
html, body { margin: 0; padding: 0; background: white; }
body > div {
  width: ${width}px;
  height: ${height}px;
  overflow: hidden;
  break-after: page;
}
body > div:last-of-type { break-after: auto; }
`
}
