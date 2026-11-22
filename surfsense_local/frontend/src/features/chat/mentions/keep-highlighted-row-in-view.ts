/** A ref for the list's rows, which exist only while it is open. The list scrolls but
 *  the popover only marks the row the arrow keys reach, so this keeps it on screen. */
export function keepHighlightedRowInView(rows: HTMLElement | null) {
  if (!rows) return
  const observer = new MutationObserver(() => {
    rows
      .querySelector("[data-highlighted]")
      ?.scrollIntoView?.({ block: "nearest" })
  })
  observer.observe(rows, {
    subtree: true,
    attributes: true,
    attributeFilter: ["data-highlighted"],
  })
  return () => observer.disconnect()
}
