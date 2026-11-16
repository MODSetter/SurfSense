import type { SVGProps } from "react"

import { cn } from "@/lib/utils"

/** OpenCode's mark in its own colours: dark on a light theme, light on a dark one. */
export function OpencodeIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      // Square, with the logo's 300 high at 83%: the margin a 24-unit library icon leaves.
      viewBox="-60 -30 360 360"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("size-4", className)}
      {...props}
    >
      <path
        d="M180 240H60V120H180V240Z"
        className="fill-[#D2D2D2] dark:fill-[#4B4B4B]"
      />
      <path
        d="M180 60H60V240H180V60ZM240 300H0V0H240V300Z"
        className="fill-[#1F1F1F] dark:fill-[#EEEEEE]"
      />
    </svg>
  )
}
