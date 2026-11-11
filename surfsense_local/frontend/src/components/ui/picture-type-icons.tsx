import type { SVGProps } from "react"

import { cn } from "@/lib/utils"

// Studio's picture types as small pictures for their cards, drawn on the
// theme's tokens so they follow light and dark. 3:2, the card's thumbnail.
const VIEW_BOX = "0 0 96 64"

/** A framed picture: hills under a sun. */
export function ImageTypeIcon({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox={VIEW_BOX}
      fill="none"
      aria-hidden="true"
      data-slot="picture-type-art"
      className={cn("size-full", className)}
      {...props}
    >
      <rect
        x="14"
        y="8"
        width="68"
        height="48"
        rx="5"
        className="fill-card stroke-foreground"
        strokeWidth="1.6"
      />
      <circle
        cx="64"
        cy="21"
        r="5.5"
        className="fill-secondary stroke-foreground"
        strokeWidth="1.4"
      />
      <path
        d="M15 45 L36 26 L52 41 L60 34 L81 51 V51.5 A3.5 3.5 0 0 1 77.5 55 H18.5 A3.5 3.5 0 0 1 15 51.5 Z"
        className="fill-muted stroke-foreground"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M15 52 L30 41 L44 50 L50 46 L64 55"
        className="stroke-muted-foreground"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M31 33 l3 -2.5 M39 30 l2.5 2"
        className="stroke-muted-foreground"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
    </svg>
  )
}

/** A sketchnote: a heading, two notes joined by an arrow, and a small chart. */
export function InfographicTypeIcon({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox={VIEW_BOX}
      fill="none"
      aria-hidden="true"
      data-slot="picture-type-art"
      className={cn("size-full", className)}
      {...props}
    >
      <rect
        x="10"
        y="6"
        width="76"
        height="52"
        rx="5"
        className="fill-card stroke-foreground"
        strokeWidth="1.6"
      />
      <rect
        x="18"
        y="12"
        width="34"
        height="5"
        rx="2.5"
        className="fill-foreground"
      />
      <rect
        x="56"
        y="13"
        width="14"
        height="3"
        rx="1.5"
        className="fill-muted-foreground"
      />
      <rect
        x="17"
        y="23"
        width="26"
        height="14"
        rx="3"
        className="fill-muted stroke-foreground"
        strokeWidth="1.2"
      />
      <path
        d="M21 28 H38 M21 32 H33"
        className="stroke-muted-foreground"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path
        d="M30 37 C30 43 34 45 40 45"
        className="stroke-foreground"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path
        d="M37.5 42.5 L40.5 45 L37.5 47.5"
        className="stroke-foreground"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="43"
        y="40"
        width="20"
        height="11"
        rx="3"
        className="fill-secondary stroke-foreground"
        strokeWidth="1.2"
      />
      <path
        d="M47 45.5 H59"
        className="stroke-muted-foreground"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path
        d="M66 50 H80"
        className="stroke-foreground"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <rect
        x="68"
        y="39"
        width="3.5"
        height="11"
        rx="1"
        className="fill-chart-3"
      />
      <rect
        x="73"
        y="31"
        width="3.5"
        height="19"
        rx="1"
        className="fill-chart-1"
      />
      <rect
        x="78"
        y="35"
        width="3.5"
        height="15"
        rx="1"
        className="fill-chart-4"
      />
      <circle
        cx="74"
        cy="24.5"
        r="3"
        className="fill-card stroke-foreground"
        strokeWidth="1.1"
      />
    </svg>
  )
}
