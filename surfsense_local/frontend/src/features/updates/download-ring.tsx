import { cn } from "@/lib/utils"

/**
 * A ring that fills clockwise from the top as a download runs. With no
 * percentage yet, a quarter of it turns instead.
 */
export function DownloadRing({
  percent,
  className,
}: {
  percent: number | null
  className?: string
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className={cn(
        "-rotate-90",
        percent === null && "animate-spin motion-reduce:animate-none",
        className
      )}
    >
      <circle
        cx="10"
        cy="10"
        r="8.75"
        fill="none"
        strokeWidth="1.5"
        className="stroke-notice/25"
      />
      <circle
        cx="10"
        cy="10"
        r="8.75"
        fill="none"
        strokeWidth="1.5"
        strokeLinecap="round"
        // pathLength 100 lets the dash be the percentage itself.
        pathLength={100}
        strokeDasharray={`${percent ?? 25} 100`}
        className="stroke-notice transition-[stroke-dasharray] duration-250 ease-out motion-reduce:transition-none"
      />
    </svg>
  )
}
