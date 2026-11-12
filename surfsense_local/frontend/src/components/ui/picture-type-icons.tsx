import { type SVGProps, useId } from "react"

import { cn } from "@/lib/utils"

// Studio's picture types as small pictures for their cards. They carry their
// own colours and backdrop, as a thumbnail does, so they read the same in light and dark.
// 3:2, the card's thumbnail.
const VIEW_BOX = "0 0 120 80"
const INK = "#1f2a44"

/** A photo print over another: a landscape under a sun, and sparks for AI. */
export function ImageTypeIcon({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const id = useId()
  const photo = `${id}-photo`
  const sky = `${id}-sky`
  const backdrop = `${id}-backdrop`
  return (
    <svg
      viewBox={VIEW_BOX}
      fill="none"
      aria-hidden="true"
      data-slot="picture-type-art"
      className={cn("size-full", className)}
      {...props}
    >
      <defs>
        <clipPath id={photo}>
          <rect x="33" y="19" width="56" height="38" rx="2.5" />
        </clipPath>
        <linearGradient id={backdrop} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffe3ee" />
          <stop offset="1" stopColor="#e2e6ff" />
        </linearGradient>
        <linearGradient id={sky} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#9fd3ff" />
          <stop offset="1" stopColor="#e3f3ff" />
        </linearGradient>
      </defs>
      <rect width="120" height="80" fill={`url(#${backdrop})`} />
      <circle cx="12" cy="10" r="16" fill="#ffffff" opacity="0.45" />
      <circle cx="112" cy="74" r="20" fill="#ffffff" opacity="0.35" />
      <ellipse cx="61" cy="73" rx="34" ry="3" fill="#000" opacity="0.12" />
      <rect
        x="30"
        y="11"
        width="62"
        height="52"
        rx="4"
        transform="rotate(-9 61 37)"
        fill="#ffd3e2"
        stroke={INK}
        strokeOpacity="0.35"
        strokeWidth="1"
      />
      <g transform="rotate(4 61 41)">
        <rect
          x="28"
          y="14"
          width="66"
          height="56"
          rx="4"
          fill="#ffffff"
          stroke={INK}
          strokeOpacity="0.45"
          strokeWidth="1.1"
        />
        <g clipPath={`url(#${photo})`}>
          <rect x="33" y="19" width="56" height="38" fill={`url(#${sky})`} />
          <circle cx="75" cy="29" r="5.5" fill="#ffc83d" />
          <path
            d="M54 27.5 a3 3 0 0 1 5.6 -1.2 a2.4 2.4 0 0 1 3.4 2.2 h-9 Z"
            fill="#ffffff"
          />
          <path
            d="M33 50 L48 32 L58 43 L67 35 L89 53 V57 H33 Z"
            fill="#7c8cf8"
          />
          <path
            d="M44.6 36.9 L48 32 L51.6 36.3 L49.6 35.3 L47.4 37.6 Z"
            fill="#ffffff"
          />
          <path d="M60 41 L67 35 L89 53 V57 H60 Z" fill="#5664e0" />
          <path
            d="M33 57 V50 C45 44 56 47 64 50 C74 54 82 49 89 47 V57 Z"
            fill="#4cc38a"
          />
          <path
            d="M33 57 V53 C44 50 52 52 60 55 C66 57 72 55 76 57 Z"
            fill="#2fa56e"
          />
        </g>
        <rect x="33" y="62" width="22" height="2.6" rx="1.3" fill="#e4e7ee" />
      </g>
      <path
        d="M98 12 C98.6 15.8 99.8 17 103.5 17.5 C99.8 18 98.6 19.2 98 23 C97.4 19.2 96.2 18 92.5 17.5 C96.2 17 97.4 15.8 98 12 Z"
        fill="#ff6fa8"
      />
      <path
        d="M22 50 C22.3 52 23 52.7 25 53 C23 53.3 22.3 54 22 56 C21.7 54 21 53.3 19 53 C21 52.7 21.7 52 22 50 Z"
        fill="#ffc83d"
      />
      <circle cx="104" cy="28" r="1.4" fill="#7c8cf8" />
    </svg>
  )
}

/** A poster of figures: a title, a donut with its legend, and a bar chart. */
export function InfographicTypeIcon({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const id = useId()
  const sheet = `${id}-sheet`
  const header = `${id}-header`
  const backdrop = `${id}-backdrop`
  return (
    <svg
      viewBox={VIEW_BOX}
      fill="none"
      aria-hidden="true"
      data-slot="picture-type-art"
      className={cn("size-full", className)}
      {...props}
    >
      <defs>
        <clipPath id={sheet}>
          <rect x="22" y="8" width="76" height="62" rx="5" />
        </clipPath>
        <linearGradient id={backdrop} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ddf7ea" />
          <stop offset="1" stopColor="#dcebff" />
        </linearGradient>
        <linearGradient id={header} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
      </defs>
      <rect width="120" height="80" fill={`url(#${backdrop})`} />
      <circle cx="108" cy="12" r="18" fill="#ffffff" opacity="0.45" />
      <circle cx="10" cy="70" r="16" fill="#ffffff" opacity="0.35" />
      <ellipse cx="60" cy="74" rx="36" ry="3" fill="#000" opacity="0.12" />
      <rect x="22" y="8" width="76" height="62" rx="5" fill="#ffffff" />
      <rect
        x="22"
        y="8"
        width="76"
        height="7"
        clipPath={`url(#${sheet})`}
        fill={`url(#${header})`}
      />
      <rect
        x="22"
        y="8"
        width="76"
        height="62"
        rx="5"
        stroke={INK}
        strokeOpacity="0.45"
        strokeWidth="1.1"
      />
      <rect x="30" y="20" width="32" height="4" rx="2" fill={INK} />
      <rect x="30" y="27" width="22" height="2.5" rx="1.25" fill="#a3acc2" />
      <circle cx="42" cy="49" r="9" strokeWidth="5" stroke="#e8ebf2" />
      <circle
        cx="42"
        cy="49"
        r="9"
        strokeWidth="5"
        strokeDasharray="24 56.5"
        transform="rotate(-90 42 49)"
        stroke="#ff7a59"
      />
      <circle
        cx="42"
        cy="49"
        r="9"
        strokeWidth="5"
        strokeDasharray="17 56.5"
        strokeDashoffset="-24"
        transform="rotate(-90 42 49)"
        stroke="#ffc83d"
      />
      <circle
        cx="42"
        cy="49"
        r="9"
        strokeWidth="5"
        strokeDasharray="15.5 56.5"
        strokeDashoffset="-41"
        transform="rotate(-90 42 49)"
        stroke="#3b82f6"
      />
      <circle cx="72" cy="21" r="2" fill="#ff7a59" />
      <rect x="76" y="20" width="14" height="2" rx="1" fill="#e4e7ee" />
      <circle cx="72" cy="27" r="2" fill="#3b82f6" />
      <rect x="76" y="26" width="10" height="2" rx="1" fill="#e4e7ee" />
      <rect x="60" y="49" width="5" height="12" rx="1" fill="#3b82f6" />
      <rect x="67.5" y="43" width="5" height="18" rx="1" fill="#22c55e" />
      <rect x="75" y="46" width="5" height="15" rx="1" fill="#ffc83d" />
      <rect x="82.5" y="37" width="5" height="24" rx="1" fill="#ff7a59" />
      <path d="M58 61.5 H90" stroke={INK} strokeOpacity="0.4" strokeWidth="1" />
      <path
        d="M60 40 L67 35 L74 38 L84 31"
        stroke="#8b5cf6"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="2 2"
      />
    </svg>
  )
}
