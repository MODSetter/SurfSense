import { useId, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"

import { DeleteModelDialog } from "./delete-model-dialog"
import { ModelRow } from "./model-row"
import type { YourModelRow } from "./your-model-row"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_local_group_request_error",
        defaultMessage: "The request failed",
      })
}

/** The slot's models on this computer; a download under way shows as `pending`. */
export function LocalModelsGroup({
  rows,
  pending,
  onDownload,
  onUse,
  onDelete,
}: {
  rows: YourModelRow[]
  pending?: ReactNode
  onDownload: () => void
  onUse: (row: YourModelRow) => Promise<unknown>
  onDelete: (row: YourModelRow) => Promise<unknown>
}) {
  const headingId = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<YourModelRow | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const run = (action: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    return action()
      .catch((cause: unknown) => {
        setError(messageFrom(cause))
        throw cause
      })
      .finally(() => setBusy(false))
  }

  const confirmDelete = () => {
    if (!deleting) return
    setDeleteError(null)
    run(() => onDelete(deleting))
      .then(() => setDeleting(null))
      .catch((cause: unknown) => setDeleteError(messageFrom(cause)))
  }

  return (
    <section className="flex flex-col gap-2" aria-labelledby={headingId}>
      <h3 id={headingId} className="text-xs font-medium text-muted-foreground">
        {intl.formatMessage({
          id: "models_local_group_title",
          defaultMessage: "This computer",
        })}
      </h3>

      {rows.length === 0 && !pending ? (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed px-3 py-2.5">
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage({
              id: "models_local_group_empty",
              defaultMessage: "Nothing downloaded yet.",
            })}
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onDownload}
          >
            {intl.formatMessage({
              id: "models_local_group_download_button",
              defaultMessage: "Download a model",
            })}
          </Button>
        </div>
      ) : (
        <ul className="divide-y overflow-hidden rounded-xl border bg-card">
          {pending ? <li className="px-3 py-2.5">{pending}</li> : null}
          {rows.map((row) => (
            <ModelRow
              key={row.key}
              row={row}
              disabled={busy}
              onUse={() => void run(() => onUse(row)).catch(() => undefined)}
              onDelete={() => {
                setDeleteError(null)
                setDeleting(row)
              }}
            />
          ))}
        </ul>
      )}

      {error && deleting === null ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <DeleteModelDialog
        row={deleting}
        pending={busy}
        error={deleteError}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </section>
  )
}
