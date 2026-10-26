import { Badge } from "@/components/ui/badge"
import { intl } from "@/i18n/intl"

import type { WebGroup } from "./api"
import { pullerName } from "./puller-names"
import type { RowActions } from "./row-actions"
import { ShowMoreButton } from "./show-more-button"
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
        <ShowMoreButton
          loading={actions.loadingMore.has(link)}
          onClick={() => actions.onMore(link)}
        />
      ) : null}
    </section>
  )
}
