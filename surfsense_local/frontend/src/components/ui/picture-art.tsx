import { type ReactNode, type SVGProps, useId } from "react"

import { cn } from "@/lib/utils"

// The frame every Studio card picture shares: a 3:2 canvas on its own
// gradient backdrop, so it reads the same in light and dark.
export const INK = "#1f2a44"

export function PictureArt({
  from,
  to,
  className,
  children,
  ...props
}: Omit<SVGProps<SVGSVGElement>, "from" | "to"> & {
  from: string
  to: string
  children: ReactNode
}) {
  const backdrop = `${useId()}-backdrop`
  return (
    <svg
      viewBox="0 0 120 80"
      fill="none"
      aria-hidden="true"
      data-slot="picture-type-art"
      className={cn("size-full", className)}
      {...props}
    >
      <defs>
        <linearGradient id={backdrop} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={from} />
          <stop offset="1" stopColor={to} />
        </linearGradient>
      </defs>
      <rect width="120" height="80" fill={`url(#${backdrop})`} />
      <circle cx="12" cy="10" r="16" fill="#ffffff" opacity="0.45" />
      <circle cx="112" cy="74" r="20" fill="#ffffff" opacity="0.35" />
      {children}
    </svg>
  )
}

/** The soft shadow a picture's object stands on. */
export function Ground({ cx = 60, rx = 32 }: { cx?: number; rx?: number }) {
  return <ellipse cx={cx} cy="74" rx={rx} ry="3" fill="#000" opacity="0.12" />
}

/** A white sheet with the ink edge every printed object has. */
export function Sheet(props: SVGProps<SVGRectElement>) {
  return (
    <rect
      rx="3"
      fill="#ffffff"
      stroke={INK}
      strokeOpacity="0.45"
      strokeWidth="1.1"
      {...props}
    />
  )
}

/** A comic panel: a flat colour inside a thin ink border. */
export function Panel(props: SVGProps<SVGRectElement>) {
  return (
    <rect
      rx="1"
      stroke={INK}
      strokeOpacity="0.7"
      strokeWidth="0.8"
      {...props}
    />
  )
}

/** A speech bubble with its tail pointing down and left. */
export function Bubble({
  cx,
  cy,
  rx = 6,
  ry = 3.5,
}: {
  cx: number
  cy: number
  rx?: number
  ry?: number
}) {
  return (
    <g>
      <path
        d={`M${cx - rx * 0.4} ${cy + ry * 0.7} L${cx - rx * 0.75} ${cy + ry + 2.5} L${cx - rx * 0.05} ${cy + ry * 0.85} Z`}
        fill="#ffffff"
        stroke={INK}
        strokeWidth="0.7"
        strokeLinejoin="round"
      />
      <ellipse
        cx={cx}
        cy={cy}
        rx={rx}
        ry={ry}
        fill="#ffffff"
        stroke={INK}
        strokeWidth="0.7"
      />
    </g>
  )
}

/** A star burst's points, as an SVG polygon takes them. */
export function burst(
  cx: number,
  cy: number,
  outer: number,
  inner: number,
  points = 10
): string {
  return Array.from({ length: points * 2 }, (_, i) => {
    const radius = i % 2 === 0 ? outer : inner
    const angle = (Math.PI * i) / points - Math.PI / 2
    return `${(cx + radius * Math.cos(angle)).toFixed(1)},${(cy + radius * Math.sin(angle)).toFixed(1)}`
  }).join(" ")
}
