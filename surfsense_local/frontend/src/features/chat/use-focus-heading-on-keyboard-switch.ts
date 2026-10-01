import { useEffect, useRef, type RefObject } from "react"

/**
 * After a thread switch the keyboard made, focus moves to the conversation's
 * heading, so a screen reader says where it landed. A pointer switch leaves the
 * composer's own focus alone: that is what lets someone click a chat and type.
 */
export function useFocusHeadingOnKeyboardSwitch(
  threadId: number | null,
  heading: RefObject<HTMLElement | null>
) {
  const keyboard = useRef(false)
  useEffect(() => {
    // A key in the composer is writing or sending, never choosing a thread:
    // a new chat's first send creates one, and the person is still writing.
    const fromKeyboard = (event: KeyboardEvent) => {
      keyboard.current = !(
        event.target instanceof Element &&
        event.target.closest("[data-composer-placement]")
      )
    }
    const fromPointer = () => {
      keyboard.current = false
    }
    document.addEventListener("keydown", fromKeyboard, true)
    document.addEventListener("pointerdown", fromPointer, true)
    return () => {
      document.removeEventListener("keydown", fromKeyboard, true)
      document.removeEventListener("pointerdown", fromPointer, true)
    }
  }, [])

  const previous = useRef(threadId)
  useEffect(() => {
    if (previous.current === threadId) return
    previous.current = threadId
    if (threadId == null || !keyboard.current) return
    // Queued, so it follows the composer's focus on the same switch.
    const timer = window.setTimeout(() => heading.current?.focus(), 0)
    return () => window.clearTimeout(timer)
  }, [threadId, heading])
}
