import { useEffect, useState } from "react"

import {
  getShaderColorFromString,
  ShaderMount,
} from "@paper-design/shaders-react"

import ditherBackground from "./onboarding-dither-background.webp"
import { onboardingDitherFragmentShader } from "./onboarding-dither-shader"

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"

// The literal hex values below are the app's own --background token plus a
// darkened variant of --muted-foreground (light) / --muted-foreground itself
// (dark), copied rather than read live: shader uniforms are numbers, not CSS
// custom properties. If those tokens move in index.css, these move with them.
const PALETTE = {
  light: { back: "#f7f6f2", front: "#4a4a4a" },
  dark: { back: "#141414", front: "#8e8a83" },
} as const

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false)

  useEffect(() => {
    const query = window.matchMedia(REDUCED_MOTION_QUERY)
    const update = () => setReduced(query.matches)
    update()
    query.addEventListener("change", update)
    return () => query.removeEventListener("change", update)
  }, [])

  return reduced
}

// Mirrors how ThemeProvider itself resolves "system": it only ever toggles a
// "light"/"dark" class on <html>, so that class is the single source of truth
// for what's actually on screen, independent of the stored preference.
function useIsDarkTheme() {
  const [isDark, setIsDark] = useState(() =>
    document.documentElement.classList.contains("dark")
  )

  useEffect(() => {
    const root = document.documentElement
    const observer = new MutationObserver(() => {
      setIsDark(root.classList.contains("dark"))
    })
    observer.observe(root, { attributes: true, attributeFilter: ["class"] })
    return () => observer.disconnect()
  }, [])

  return isDark
}

/**
 * The onboarding welcome step's animated, dithered backdrop.
 *
 * A WebGL filter over `onboarding-dither-background.webp`, mounted through
 * the library's generic `ShaderMount` with a custom fragment shader — see
 * `onboarding-dither-shader.ts` for why a stock shader won't do and how the
 * motion is produced. Ported from the marketing site's homepage hero
 * (`surfsense_web`), full-screen instead of confined to a hero section.
 *
 * Under `prefers-reduced-motion` the speed drops to 0, which stops the frame
 * loop entirely and pins the filter to a single frame — the pattern still
 * draws, it just stops moving.
 */
export function OnboardingDither({ fading = false }: { fading?: boolean }) {
  const reducedMotion = usePrefersReducedMotion()
  const isDark = useIsDarkTheme()
  const palette = isDark ? PALETTE.dark : PALETTE.light

  return (
    <div
      className="ss-onboarding-dither transition-opacity duration-200 ease-out motion-reduce:transition-none"
      // Inline, since `.ss-onboarding-dither` sets its own opacity outside
      // Tailwind's layers and would win over a utility.
      style={fading ? { opacity: 0 } : undefined}
      aria-hidden="true"
    >
      <ShaderMount
        fragmentShader={onboardingDitherFragmentShader}
        speed={reducedMotion || fading ? 0 : 1}
        uniforms={{
          u_image: ditherBackground,
          u_colorBack: getShaderColorFromString(palette.back),
          u_colorFront: getShaderColorFromString(palette.front),
          // Same as front: the shader swaps to the highlight above ~96%
          // brightness, and the drifting grain pushes crest cells over that
          // line, so a distinct highlight would flash pale pixels. Matching
          // it to the ink gives classic two-colour dithering.
          u_colorHighlight: getShaderColorFromString(palette.front),
          u_type: 4, // 8x8 Bayer
          u_pxSize: 3,
          u_colorSteps: 3,
          u_flow: 1,
          u_fit: 2, // cover
          u_scale: 1,
          u_rotation: 0,
          u_offsetX: 0,
          u_offsetY: 0,
          u_originX: 0.5,
          u_originY: 0.5,
          u_worldWidth: 0,
          u_worldHeight: 0,
        }}
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  )
}
