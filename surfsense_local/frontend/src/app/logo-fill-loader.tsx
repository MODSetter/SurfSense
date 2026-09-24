import surfSenseLogo from "@/surfsense-logo.svg"
import { cn } from "@/lib/utils"

// The logo is the mask, as in onboarding's brand row, so its paths are drawn
// once by the browser rather than copied into the page.
const LOGO_MASK = {
  maskImage: `url(${surfSenseLogo})`,
  maskPosition: "center",
  maskRepeat: "no-repeat",
  maskSize: "contain",
} as const

/**
 * The logo filling with a rippling tide, looped until the app is ready: a
 * faint logo, and a solid one rising through it behind a wave. The motion is
 * in `index.css` (`ss-logo-fill-*`); under reduced motion it rests full.
 */
export function LogoFillLoader({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("relative size-14 overflow-hidden", className)}
      style={LOGO_MASK}
    >
      <div className="absolute inset-0 bg-foreground/15" />
      <div className="ss-logo-fill-liquid absolute inset-x-0 top-0 flex h-[calc(100%+0.5rem)] flex-col">
        {/* Two periods of the wave, so sliding it by half loops seamlessly. */}
        <svg
          aria-hidden="true"
          focusable="false"
          viewBox="0 0 200 16"
          preserveAspectRatio="none"
          className="ss-logo-fill-wave block h-2 w-[200%] shrink-0 fill-foreground"
        >
          <path d="M0 8 Q25 0 50 8 T100 8 T150 8 T200 8 V16 H0 Z" />
        </svg>
        <div className="flex-1 bg-foreground" />
      </div>
    </div>
  )
}
