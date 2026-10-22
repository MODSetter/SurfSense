import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { WebGroup } from "./api"
import { WebResultRow, type RowState } from "./web-result-row"

/** A search's results, the single links pasted, or one list's items with Show more. */
export function WebResultGroup({
  group,
  states,
  loadingMore,
  onAdd,
  onOpen,
  onMore,
}: {
  group: WebGroup
  states: ReadonlyMap<string, RowState>
  loadingMore: boolean
  onAdd: (url: string) => void
  onOpen: (url: string) => void
  onMore: (link: string) => void
}) {
  return (
    <section className="flex flex-col">
      {group.link ? (
        <p className="truncate px-3 pt-2 text-xs font-medium text-muted-foreground">
          {group.link}
        </p>
      ) : null}
      {group.failed ? (
        <p className="px-3 py-2 text-sm text-destructive">
          {intl.formatMessage({
            id: "sources_web_list_failed_error",
            defaultMessage: "Couldn’t open this list. Try again later.",
          })}
        </p>
      ) : group.results.length === 0 ? (
        <p className="px-3 py-6 text-center text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "sources_web_results_empty",
            defaultMessage: "No results. Try other words.",
          })}
        </p>
      ) : (
        <ul className="flex flex-col">
          {group.results.map((result) => (
            <WebResultRow
              key={result.url}
              result={result}
              state={states.get(result.url)}
              onAdd={onAdd}
              onOpen={onOpen}
            />
          ))}
        </ul>
      )}
      {group.link && group.more ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="self-start"
          disabled={loadingMore}
          onClick={() => onMore(group.link as string)}
        >
          {loadingMore ? <Spinner /> : null}
          {intl.formatMessage({
            id: "sources_web_show_more_button",
            defaultMessage: "Show more",
          })}
        </Button>
      ) : null}
    </section>
  )
}
