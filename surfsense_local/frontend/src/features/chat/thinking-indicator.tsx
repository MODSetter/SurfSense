import { memo, useId, type CSSProperties, type ReactNode } from "react"

import { cn } from "@/lib/utils"

// Ported from surfsense_web's timeline activity indicator. Motion lives in
// `index.css` under `.ss-thinking-*`; fills are theme tokens set there too,
// because the web's white-on-screen dots vanish on a light background.

type DotStyle = CSSProperties & Record<`--ss-thinking-${string}`, string>

const DOTS = [
  {
    id: "east",
    pair: "a",
    x: 6.1,
    y: 0,
    burstX: 7.2,
    burstY: 0,
    pulseDuration: 1.92,
    pulseDelay: -0.35,
    breathePrimaryDelay: -3.96,
    breatheSecondaryDelay: 0,
  },
  {
    id: "south-east",
    pair: "b",
    x: 3.05,
    y: 5.28,
    burstX: 3.6,
    burstY: 6.24,
    pulseDuration: 2.18,
    pulseDelay: -1.15,
    breathePrimaryDelay: -0.506,
    breatheSecondaryDelay: -0.542,
  },
  {
    id: "south-west",
    pair: "c",
    x: -3.05,
    y: 5.28,
    burstX: -3.6,
    burstY: 6.24,
    pulseDuration: 2.43,
    pulseDelay: -0.6,
    breathePrimaryDelay: -3.867,
    breatheSecondaryDelay: -1.083,
  },
  {
    id: "west",
    pair: "a",
    x: -6.1,
    y: 0,
    burstX: -7.2,
    burstY: 0,
    pulseDuration: 2.06,
    pulseDelay: -1.7,
    breathePrimaryDelay: -3.043,
    breatheSecondaryDelay: -1.625,
  },
  {
    id: "north-west",
    pair: "b",
    x: -3.05,
    y: -5.28,
    burstX: -3.6,
    burstY: -6.24,
    pulseDuration: 2.31,
    pulseDelay: -0.95,
    breathePrimaryDelay: -3.763,
    breatheSecondaryDelay: -2.167,
  },
  {
    id: "north-east",
    pair: "c",
    x: 3.05,
    y: -5.28,
    burstX: 3.6,
    burstY: -6.24,
    pulseDuration: 2.54,
    pulseDelay: -2.1,
    breathePrimaryDelay: -2.719,
    breatheSecondaryDelay: -2.708,
  },
] as const

const dotStyles = DOTS.map((dot) => ({
  id: dot.id,
  pair: dot.pair,
  style: {
    "--ss-thinking-x": `${dot.x}px`,
    "--ss-thinking-y": `${dot.y}px`,
    "--ss-thinking-cross-x": `${-dot.x}px`,
    "--ss-thinking-cross-y": `${-dot.y}px`,
    "--ss-thinking-burst-x": `${dot.burstX}px`,
    "--ss-thinking-burst-y": `${dot.burstY}px`,
    "--ss-thinking-pulse-x": `${dot.x * 0.075}px`,
    "--ss-thinking-pulse-y": `${dot.y * 0.075}px`,
    "--ss-thinking-recoil-x": `${dot.x * -0.0315}px`,
    "--ss-thinking-recoil-y": `${dot.y * -0.0315}px`,
    "--ss-thinking-pulse-duration": `${dot.pulseDuration}s`,
    "--ss-thinking-pulse-delay": `${dot.pulseDelay}s`,
    "--ss-thinking-breathe-primary-delay": `${dot.breathePrimaryDelay}s`,
    "--ss-thinking-breathe-secondary-delay": `${dot.breatheSecondaryDelay}s`,
  } as DotStyle,
}))

/** Six dots that orbit, merge and burst while the model thinks. */
export const ThinkingIndicator = memo(function ThinkingIndicator({
  className,
}: {
  className?: string
}) {
  const id = useId()
  const bloomFilterId = `${id}-bloom`
  const fringeFilterId = `${id}-fringe`
  const gooFilterId = `${id}-goo`

  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      className={cn(
        "ss-thinking-indicator block size-6 shrink-0 overflow-visible",
        className
      )}
    >
      <defs>
        <filter
          id={bloomFilterId}
          x="-150%"
          y="-150%"
          width="400%"
          height="400%"
          colorInterpolationFilters="sRGB"
        >
          <feGaussianBlur stdDeviation="1.65" />
        </filter>
        <filter
          id={fringeFilterId}
          x="-80%"
          y="-80%"
          width="260%"
          height="260%"
          colorInterpolationFilters="sRGB"
        >
          <feGaussianBlur stdDeviation="0.55" />
        </filter>
        <filter
          id={gooFilterId}
          x="-50%"
          y="-50%"
          width="200%"
          height="200%"
          colorInterpolationFilters="sRGB"
        >
          <feGaussianBlur in="SourceGraphic" stdDeviation="0.8" result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 15 -5.5"
          />
        </filter>
      </defs>
      <g className="ss-thinking-goo" filter={`url(#${gooFilterId})`}>
        <Orbit>
          <circle cx="12" cy="12" r="1.7" className="ss-thinking-core" />
        </Orbit>
      </g>
      <g className="ss-thinking-light">
        <Orbit>
          <circle
            cx="12"
            cy="12"
            r="2.15"
            opacity="0.42"
            filter={`url(#${bloomFilterId})`}
            className="ss-thinking-glow"
          />
          <circle
            cx="11.68"
            cy="12.06"
            r="1.85"
            opacity="0.62"
            filter={`url(#${fringeFilterId})`}
            className="ss-thinking-cool"
          />
          <circle
            cx="12.32"
            cy="12.06"
            r="1.85"
            opacity="0.58"
            filter={`url(#${fringeFilterId})`}
            className="ss-thinking-warm"
          />
          <circle cx="12" cy="12" r="1.58" className="ss-thinking-core" />
        </Orbit>
      </g>
    </svg>
  )
})

function Orbit({ children }: { children: ReactNode }) {
  return (
    <g className="ss-thinking-orbit">
      {dotStyles.map(({ id, pair, style }) => (
        <g
          key={id}
          className={`ss-thinking-dot ss-thinking-dot-${pair}`}
          style={style}
        >
          <g className="ss-thinking-pulse">
            <g className="ss-thinking-breathe-primary">
              <g className="ss-thinking-breathe-secondary">{children}</g>
            </g>
          </g>
        </g>
      ))}
    </g>
  )
}
