import { useEffect, useState } from "react"

import { ImageDithering } from "@paper-design/shaders-react"

import ditherBackground from "./onboarding-dither-background.webp"

/** The fade out once the welcome is left; the dither unmounts as it ends. */
const FADE_OUT_MS = 150

/**
 * The onboarding welcome step's dithered backdrop: the library's image dither
 * over `onboarding-dither-background.webp`, each dot inked with the image's
 * own colour. Static, so there is no frame loop to pause for reduced motion.
 */
export function OnboardingDither({ visible }: { visible: boolean }) {
  const fading = !visible
  // The welcome is never shown again, so a finished fade stays finished.
  const [gone, setGone] = useState(false)
  useEffect(() => {
    if (visible) return
    const timer = window.setTimeout(() => setGone(true), FADE_OUT_MS)
    return () => window.clearTimeout(timer)
  }, [visible])

  if (gone) return null

  return (
    <div
      className="ss-onboarding-dither transition-opacity ease-out motion-reduce:transition-none"
      // Inline, since `.ss-onboarding-dither` sets its own opacity outside
      // Tailwind's layers and would win over a utility; the duration shares
      // FADE_OUT_MS with the unmount.
      style={{
        transitionDuration: `${FADE_OUT_MS}ms`,
        ...(fading && { opacity: 0 }),
      }}
      aria-hidden="true"
    >
      <ImageDithering
        image={ditherBackground}
        originalColors
        type="8x8"
        size={3}
        colorSteps={3}
        fit="cover"
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  )
}
