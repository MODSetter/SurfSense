import { Button } from "@/components/ui/button"

import type { DownloadStep } from "./api"

export function AudioDownloadProgress({
  label,
  step,
  onCancel,
}: {
  label: string
  step: DownloadStep
  onCancel: () => void
}) {
  const percent =
    step.total > 0
      ? Math.min(100, Math.round((step.completed / step.total) * 100))
      : null

  return (
    <div className="flex items-center gap-3">
      <div
        className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={`Downloading ${label}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent ?? undefined}
      >
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${percent ?? 8}%` }}
        />
      </div>
      <span className="w-9 text-right text-xs text-muted-foreground tabular-nums">
        {percent === null ? "" : `${percent}%`}
      </span>
      <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  )
}
