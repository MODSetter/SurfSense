import { useState } from "react"

// A key for a dialog's own state: it changes on open, so the form starts
// fresh, and not on close, which would remount it mid exit animation.
export function useDialogOpening(open: boolean) {
  const [seen, setSeen] = useState({ open, opening: 0 })
  const opening = open && !seen.open ? seen.opening + 1 : seen.opening
  if (open !== seen.open) setSeen({ open, opening })
  return opening
}

// For a dialog that is only rendered while it has something to show: it stays
// rendered on the last payload, so it can animate closed instead of vanishing.
export function useDialogPayload<T>(value: T | null) {
  const opening = useDialogOpening(value !== null)
  const [held, setHeld] = useState(value)
  if (value !== null && value !== held) setHeld(value)
  return { payload: value ?? held, opening }
}
