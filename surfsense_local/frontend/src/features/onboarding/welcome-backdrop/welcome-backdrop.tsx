import { useEffect, useMemo, useState } from "react"

import { GradientAscii } from "./gradient-ascii"
import { useDarkTheme } from "./use-dark-theme"

/** The fade out once the welcome is left; the backdrop unmounts as it ends. */
const FADE_OUT_MS = 150

// Shadow edge to brightest, topping out at `--primary`: ending on
// `--foreground` lit the whole sky near white. In light, `--primary` is near
// black, so the ink stays neutral rather than peach, as the headline's does.
const RAMP_TOKENS = ["--muted", "--muted-foreground", "--primary"]

/**
 * The onboarding welcome step's backdrop: a slow ASCII horizon in the theme's
 * own colours. Clicks are left alone, since the start button sits on top.
 */
export function WelcomeBackdrop({ visible }: { visible: boolean }) {
  const fading = !visible
  // The welcome is never shown again, so a finished fade stays finished.
  const [gone, setGone] = useState(false)
  useEffect(() => {
    if (visible) return
    const timer = window.setTimeout(() => setGone(true), FADE_OUT_MS)
    return () => window.clearTimeout(timer)
  }, [visible])

  const dark = useDarkTheme()
  // The shader parses plain colours, not `var()`, so the tokens are resolved here.
  const colors = useMemo(() => {
    const style = getComputedStyle(document.documentElement)
    return RAMP_TOKENS.map((token) => style.getPropertyValue(token).trim())
    // `dark` is what changes the tokens' values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark])
  const fontFamily = useMemo(
    () =>
      getComputedStyle(document.documentElement)
        .getPropertyValue("--font-mono")
        .trim() || "monospace",
    []
  )

  if (gone) return null

  return (
    <div
      className="ss-onboarding-backdrop transition-opacity ease-out motion-reduce:transition-none"
      // Inline, since `.ss-onboarding-backdrop` sets its own opacity outside
      // Tailwind's layers and would win over a utility; the duration shares
      // FADE_OUT_MS with the unmount.
      style={{
        transitionDuration: `${FADE_OUT_MS}ms`,
        ...(fading && { opacity: 0 }),
      }}
      aria-hidden="true"
    >
      <GradientAscii
        colors={colors}
        shape="horizon"
        lightMode={!dark}
        // A faint wash, so the characters carry the shape rather than
        // dissolving into a solid gradient behind the copy.
        gradientOpacity={0.15}
        glyphOpacity={1}
        glow={0.35}
        cellSize={14}
        speed={0.5}
        // The default 2.4s left the top of the window empty for too long.
        introSeconds={0.5}
        clickEffect="none"
        fontFamily={fontFamily}
      />
    </div>
  )
}
