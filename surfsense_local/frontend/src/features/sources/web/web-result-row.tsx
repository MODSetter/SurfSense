import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CheckIcon } from "@/components/ui/icons"
import { OverflowTooltip } from "@/components/ui/overflow-tooltip"
import { Spinner } from "@/components/ui/spinner"
import { ExternalLinkDialog } from "@/features/external-links/external-link-dialog"
import { intl } from "@/i18n/intl"

import type { WebResult } from "./api"
import { pullerName } from "./puller-names"
import { ResultDetails } from "./result-details"
import { ResultLink } from "./result-link"
import type { RowActions, RowState } from "./row-actions"

/** One link to add: its title, its whole address, and Add. */
export function WebResultRow({
  result,
  actions,
}: {
  result: WebResult
  actions: RowActions
}) {
  return (
    <li className="flex items-start gap-3 px-3 py-2.5">
      <RowText result={result} />
      <RowAction
        result={result}
        state={actions.states.get(result.url)}
        onAdd={actions.onAdd}
      />
    </li>
  )
}

function RowText({ result }: { result: WebResult }) {
  const name = pullerName(result.puller)
  const [confirming, setConfirming] = useState(false)
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-0.5">
      <span className="flex min-w-0 items-center gap-2">
        {name ? (
          <Badge variant="secondary" className="shrink-0">
            {name}
          </Badge>
        ) : null}
        <span className="truncate font-medium">{result.title}</span>
      </span>
      <span className="flex min-w-0 text-xs text-muted-foreground">
        <OverflowTooltip
          label={result.url}
          render={
            <ResultLink
              href={result.url}
              onOpen={() => setConfirming(true)}
              className="truncate"
            >
              {result.url}
            </ResultLink>
          }
        />
      </span>
      <ExternalLinkDialog
        url={result.url}
        open={confirming}
        onOpenChange={setConfirming}
      />
      {result.description ? <ResultDetails text={result.description} /> : null}
    </div>
  )
}

function RowAction({
  result,
  state,
  onAdd,
}: {
  result: WebResult
  state: RowState | undefined
  onAdd: (url: string) => void
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
