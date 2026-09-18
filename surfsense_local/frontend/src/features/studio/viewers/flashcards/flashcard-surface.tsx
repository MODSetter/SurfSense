import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

// Ported from surfsense_web's flip card, minus the `motion/react` dependency
// this app doesn't have — a plain CSS transform transition gives the same
// 3D flip without pulling in framer-motion for one component.
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"

function Face({
  children,
  hidden,
  className,
}: {
  children: ReactNode
  hidden: boolean
  className?: string
}) {
  return (
    <div
      aria-hidden={hidden}
      inert={hidden}
      style={{ backfaceVisibility: "hidden" }}
      className={cn(
        "absolute inset-0 overflow-y-auto rounded-2xl border bg-card px-6 py-8 sm:px-10 sm:py-12",
        className
      )}
    >
      {children}
    </div>
  )
}

export function FlashcardSurface({
  front,
  back,
  revealed,
  onFlip,
}: {
  front: ReactNode
  back: ReactNode
  revealed: boolean
  onFlip: () => void
}) {
  const reducedMotion =
    window.matchMedia?.(REDUCED_MOTION_QUERY).matches ?? false

  if (reducedMotion) {
    return (
      <div className="relative h-full overflow-hidden rounded-2xl border bg-card shadow-lg">
        <div className="h-full overflow-y-auto px-6 py-8 sm:px-10 sm:py-12">
          {revealed ? back : front}
        </div>
        <button
          type="button"
          onClick={onFlip}
          className="absolute inset-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label={revealed ? "Show question" : "Reveal answer"}
        />
      </div>
    )
  }

  return (
    <div className="relative h-full [perspective:2000px]">
      <div
        className="relative h-full rounded-2xl shadow-lg transition-transform duration-[450ms] ease-in-out [transform-style:preserve-3d]"
        style={{ transform: revealed ? "rotateY(180deg)" : "rotateY(0deg)" }}
      >
        <Face hidden={revealed}>{front}</Face>
        <Face hidden={!revealed} className="[transform:rotateY(180deg)]">
          {back}
        </Face>
      </div>
      <button
        type="button"
        onClick={onFlip}
        className="absolute inset-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        aria-label={revealed ? "Show question" : "Reveal answer"}
      />
    </div>
  )
}
