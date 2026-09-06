import {
  CheckIcon,
  CircleAlertIcon,
  DownloadIcon,
  HardDriveDownloadIcon,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"

import { useCatalog, type CatalogRow, type PullState } from "./use-catalog"

function PullProgressBar({
  pull,
}: {
  pull: Extract<PullState, { status: "pulling" }>
}) {
  const { label, percent, detail } = pull
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Spinner className="size-3.5" />
        <span className="truncate">
          {detail ? `${label} · ${detail}` : label}
        </span>
        {percent !== null ? (
          <span className="ml-auto tabular-nums">{percent}%</span>
        ) : null}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${percent ?? 0}%` }}
        />
      </div>
    </div>
  )
}

function CatalogRowItem({
  row,
  pull,
  onPull,
}: {
  row: CatalogRow
  pull: PullState
  onPull: () => void
}) {
  const isDone = row.installed || pull.status === "done"
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-medium">{row.label}</span>
          <span className="text-xs text-muted-foreground">
            {row.provider} · {row.size_gb} GB
          </span>
        </div>
        {isDone ? (
          <Badge variant="secondary">
            <CheckIcon data-icon="inline-start" />
            Installed
          </Badge>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={pull.status === "pulling"}
            onClick={onPull}
          >
            <DownloadIcon data-icon="inline-start" />
            {pull.status === "error" ? "Retry" : "Download"}
          </Button>
        )}
      </div>

      {pull.status === "pulling" ? <PullProgressBar pull={pull} /> : null}
      {pull.status === "error" ? (
        <p className="text-xs text-destructive">{pull.message}</p>
      ) : null}
    </div>
  )
}

export function ModelCatalog({
  providers,
  onPulled,
}: {
  providers: string[]
  onPulled: () => void
}) {
  const { state, pulls, pull, rowKey } = useCatalog(providers, onPulled)

  if (state.status === "loading") {
    return (
      <div className="flex flex-col gap-2" aria-label="Loading model catalog">
        {[0, 1, 2].map((item) => (
          <Skeleton key={item} className="h-16 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (state.status === "error") {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Could not load the model catalog</AlertTitle>
        <AlertDescription>{state.message}</AlertDescription>
      </Alert>
    )
  }

  if (state.rows.length === 0) {
    return (
      <Alert>
        <HardDriveDownloadIcon />
        <AlertTitle>No downloadable models</AlertTitle>
        <AlertDescription>
          Your local provider has no catalog to download from.
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <ScrollArea className="h-72">
      <div className="flex flex-col gap-2 pr-3">
        {state.rows.map((row) => {
          const key = rowKey(row)
          return (
            <CatalogRowItem
              key={key}
              row={row}
              pull={pulls[key] ?? { status: "idle" }}
              onPull={() => pull(row)}
            />
          )
        })}
      </div>
    </ScrollArea>
  )
}
