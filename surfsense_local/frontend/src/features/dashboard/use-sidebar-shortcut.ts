import { useEffect } from "react"

/**
 * ⌘B or Ctrl+B. In the capture phase, so it wins over a text box's bold: the
 * composer sends plain text, and nothing else in the app binds the key.
 */
export function useSidebarShortcut(onToggle: () => void) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.shiftKey || event.altKey) {
        return
      }
      if (event.key.toLowerCase() !== "b") return
      event.preventDefault()
      event.stopPropagation()
      onToggle()
    }
    window.addEventListener("keydown", onKeyDown, { capture: true })
    return () =>
      window.removeEventListener("keydown", onKeyDown, { capture: true })
  }, [onToggle])
}
