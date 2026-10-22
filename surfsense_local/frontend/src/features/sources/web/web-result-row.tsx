import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CheckIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { WebResult } from "./api"
import { pullerName } from "./puller-names"
import { refusalText } from "./refusal-text"

// Where a row stands since the dialog opened.
export type RowState = "adding" | "added" | "already" | "opening" | "opened"

/** One link to add, a list to open, or a short link that says why it can't be added. */
export function WebResultRow({
  result,
  state,
  onAdd,
  onOpen,
}: {
  result: WebResult
  state: RowState | undefined
  onAdd: (url: string) => void
  onOpen: (url: string) => void
}) {
  const name = pullerName(result.puller)
  return (
    <li className="flex items-start gap-3 rounded-md px-3 py-2.5">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="line-clamp-1 font-medium break-all">
          {result.title}
        </span>
        <span className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
          <span className="truncate">{result.site}</span>
          {name ? <Badge variant="secondary">{name}</Badge> : null}
        </span>
        {result.description ? (
          <span className="line-clamp-2 text-sm text-muted-foreground">
            {result.description}
          </span>
        ) : null}
        {result.fit === "short_link" ? (
          <span className="text-sm text-muted-foreground">
            {refusalText("short_link")}
          </span>
        ) : null}
      </div>
      <RowAction result={result} state={state} onAdd={onAdd} onOpen={onOpen} />
    </li>
  )
}

function RowAction({
  result,
  state,
  onAdd,
  onOpen,
}: {
  result: WebResult
  state: RowState | undefined
  onAdd: (url: string) => void
  onOpen: (url: string) => void
}) {
  if (state === "added" || state === "already") {
    return (
      <span className="flex shrink-0 items-center gap-1 pt-1 text-sm text-muted-foreground">
        <CheckIcon aria-hidden="true" className="size-4" />
        {state === "added"
          ? intl.formatMessage({
              id: "sources_web_added_status",
              defaultMessage: "Added",
            })
          : intl.formatMessage({
              id: "sources_web_already_status",
              defaultMessage: "Already in Sources",
            })}
      </span>
    )
  }
  if (result.fit === "one") {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="shrink-0"
        disabled={state === "adding"}
        aria-label={intl.formatMessage(
          { id: "sources_web_add_row_aria", defaultMessage: "Add {title}" },
          { title: result.title }
        )}
        onClick={() => onAdd(result.url)}
      >
        {state === "adding" ? <Spinner /> : null}
        {intl.formatMessage({
          id: "sources_web_add_row_button",
          defaultMessage: "Add",
        })}
      </Button>
    )
  }
  if (result.fit === "list") {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="shrink-0"
        disabled={state === "opening" || state === "opened"}
        aria-label={intl.formatMessage(
          { id: "sources_web_open_row_aria", defaultMessage: "Open {title}" },
          { title: result.title }
        )}
        onClick={() => onOpen(result.url)}
      >
        {state === "opening" ? <Spinner /> : null}
        {intl.formatMessage({
          id: "sources_web_open_row_button",
          defaultMessage: "Open",
        })}
      </Button>
    )
  }
  return null
}
