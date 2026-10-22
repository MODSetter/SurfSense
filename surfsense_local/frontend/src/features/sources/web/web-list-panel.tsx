import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { WebGroup } from "./api"
import { pullerName } from "./puller-names"
import type { RowActions } from "./row-actions"
import { WebResultRows } from "./web-result-rows"

/** A list's items in one panel, named after the list, so they read as one group. */
export function WebListPanel({
  title,
  group,
  actions,
}: {
  title: string
  group: WebGroup
  actions: RowActions
}) {
  const link = group.link as string
  const name = pullerName(group.results[0]?.puller ?? "")
  return (
    <section
      role="group"
      aria-label={title}
      // No overflow clip: it would stop Show more sticking to the scroll box.
      className="flex flex-col rounded-lg border bg-muted/40"
    >
      <header className="flex min-w-0 items-center gap-2 border-b px-3 py-2">
        <span className="truncate text-sm font-medium">{title}</span>
        {name ? <Badge variant="secondary">{name}</Badge> : null}
        {group.failed ? null : (
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {intl.formatMessage(
              {
                id: "sources_web_list_count_status",
                defaultMessage:
                  "{count, plural, one {# item} other {# items}}{more, select, true {, more to show} other {}}",
              },
              { count: group.results.length, more: String(group.more) }
            )}
          </span>
        )}
      </header>
      {group.failed ? (
        <p className="px-3 py-2 text-sm text-destructive">
          {intl.formatMessage({
            id: "sources_web_list_failed_error",
            defaultMessage: "Couldn’t open this list. Try again later.",
          })}
        </p>
      ) : (
        <WebResultRows results={group.results} actions={actions} />
      )}
      {group.more ? (
        // Pinned to the bottom of the results while this list is in view: a
        // long list would otherwise hide it below its last item.
        <div className="sticky bottom-0 rounded-b-lg border-t bg-popover">
          <div className="rounded-b-lg bg-muted/40 p-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={actions.loadingMore.has(link)}
              onClick={() => actions.onMore(link)}
            >
              {actions.loadingMore.has(link) ? <Spinner /> : null}
              {intl.formatMessage({
                id: "sources_web_show_more_button",
                defaultMessage: "Show more",
              })}
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
