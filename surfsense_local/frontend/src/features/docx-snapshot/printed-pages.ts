/**
 * Whether the page at a 0-based index is among printToPDF's 1-based `ranges`,
 * such as "1-4,7". With no ranges, or ones this cannot read, every page is.
 */
export function printedPages(
  ranges: string | null
): (index: number) => boolean {
  if (!ranges) return () => true
  const spans: [number, number][] = []
  for (const part of ranges.split(",")) {
    const match = /^\s*(\d+)\s*(?:-\s*(\d+))?\s*$/.exec(part)
    if (!match) return () => true
    const first = Number(match[1])
    spans.push([first, match[2] === undefined ? first : Number(match[2])])
  }
  return (index) =>
    spans.some(([first, last]) => index + 1 >= first && index + 1 <= last)
}
