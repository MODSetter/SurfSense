import { useEffect, useState } from "react"

// Cmd on macOS, Ctrl everywhere else — the same modifier this app's other
// shortcuts read via event.metaKey/event.ctrlKey (see theme-provider.tsx).
export function useModifierHeld() {
  const [held, setHeld] = useState(false)

  useEffect(() => {
    const sync = (event: KeyboardEvent) => {
      setHeld(event.metaKey || event.ctrlKey)
    }
    // A window switch (Cmd+Tab) never fires keyup for the held key, so the
    // state would otherwise get stuck "held" until the next keypress.
    const clear = () => setHeld(false)

    window.addEventListener("keydown", sync)
    window.addEventListener("keyup", sync)
    window.addEventListener("blur", clear)
    return () => {
      window.removeEventListener("keydown", sync)
      window.removeEventListener("keyup", sync)
      window.removeEventListener("blur", clear)
    }
  }, [])

  return held
}
