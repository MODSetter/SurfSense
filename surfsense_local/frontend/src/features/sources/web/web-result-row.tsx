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
import { refusalText } from "./refusal-text"
import { ResultDetails } from "./result-details"
import { ResultLink } from "./result-link"
import type { RowActions, RowState } from "./row-actions"
import { WebListPanel } from "./web-list-panel"

/**
 * One link to add, a list to open, or a short link that says why it can't be
 * added. An opened list shows its items beneath it, so they read as its own.
 */
export function WebResultRow({
  result,
  actions,
}: {
  result: WebResult
  actions: RowActions
}) {
  const state = actions.states.get(result.url)
  const opened =
    result.fit === "list" ? actions.lists.get(result.url) : undefined
  return (
    <li className="flex flex-col gap-2 px-3 py-2.5">
      <div className="flex items-start gap-3">
        <RowText result={result} />
        <RowAction
          result={result}
          state={state}
          onAdd={actions.onAdd}
          onOpen={actions.onOpen}
        />
      </div>
      {opened ? (
        <WebListPanel title={result.title} group={opened} actions={actions} />
      ) : null}
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
      {result.fit === "short_link" ? (
        <span className="text-sm text-muted-foreground">
          {refusalText("short_link")}
        </span>
      ) : null}
    </div>
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
