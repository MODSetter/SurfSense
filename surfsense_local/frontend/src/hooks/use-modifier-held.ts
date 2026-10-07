import { useCallback, useEffect, useState } from "react"

type Modifiers = { metaKey: boolean; ctrlKey: boolean }

// Cmd on macOS, Ctrl everywhere else — the same modifier this app's other
// shortcuts read via event.metaKey/event.ctrlKey (see theme-provider.tsx).
// It listens only while `enabled`: a list enables it for the one row hovered,
// not for each of its rows. `seed` reads a pointer event's modifiers, for a key
// pressed before the pointer arrived, whose keydown reached no listener.
export function useModifierHeld(enabled: boolean) {
  const [held, setHeld] = useState(false)

  useEffect(() => {
    if (!enabled) return
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
  }, [enabled])

  const seed = useCallback(
    (event: Modifiers) => setHeld(event.metaKey || event.ctrlKey),
    []
  )

  return [enabled && held, seed] as const
}
