import { ComposerPrimitive, type TriggerItem } from "@assistant-ui/react"

import { FileIcon, Folder01Icon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { FORMAT_ICONS } from "@/features/studio/studio-formats"

import { mentionGroupLabel } from "./mention-group-label"
import { isFolderItem } from "./mention-items"
import { MentionItem, MentionItemDescription } from "./mention-list"
import { MentionRowsSkeleton } from "./mention-list-skeleton"
import { useMentionPopoverScope } from "./mention-popover-scope"
import { useRowsLoadedOnScroll } from "./use-rows-loaded-on-scroll"

function RowIcon({ item }: { item: TriggerItem }) {
  const Icon = isFolderItem(item)
    ? Folder01Icon
    : (FORMAT_ICONS[String(item.metadata?.format)] ?? FileIcon)
  return <Icon className="size-4 shrink-0 text-muted-foreground" />
}

function LoadedRows({
  found,
  grouped,
}: {
  found: readonly TriggerItem[]
  // A search mixes the groups, so it names them; one opened group already is.
  grouped: boolean
}) {
  const { shown, rows } = useRowsLoadedOnScroll(found.length)
  return (
    <div ref={rows} className="contents">
      {found.slice(0, shown).map((item, index) => (
        <div key={item.id} className="contents">
          {grouped && found[index - 1]?.type !== item.type ? (
            <p
              role="presentation"
              className="px-2 pt-1.5 pb-1 text-xs text-muted-foreground select-none"
            >
              {mentionGroupLabel(item.type)}
            </p>
          ) : null}
          <MentionItem
            render={
              <ComposerPrimitive.TriggerPopoverItem item={item} index={index} />
            }
            className="data-highlighted:bg-accent"
          >
            <RowIcon item={item} />
            <span className="min-w-0 truncate">{item.label}</span>
            {item.description ? (
              <MentionItemDescription>
                {item.description}
              </MentionItemDescription>
            ) : null}
          </MentionItem>
        </div>
      ))}
    </div>
  )
}

function emptyMessage(group: string | null) {
  if (group === null) {
    return intl.formatMessage({
      id: "chat_mentions_no_match_empty",
      defaultMessage: "Nothing matches",
    })
  }
  return group === "artifact"
    ? intl.formatMessage({
        id: "chat_mentions_no_artifacts_empty",
        defaultMessage: "No artifacts yet.",
      })
    : intl.formatMessage({
        id: "chat_mentions_no_sources_empty",
        defaultMessage: "No sources yet.",
      })
}

/** An opened group's rows, or a search's. */
export function MentionRows({
  found,
  isLoading,
}: {
  found: readonly TriggerItem[]
  isLoading: boolean
}) {
  const { activeCategoryId, query } = useMentionPopoverScope()
  if (found.length === 0) {
    return isLoading ? (
      <MentionRowsSkeleton />
    ) : (
      <p className="px-2 py-1.5 text-sm text-muted-foreground">
        {emptyMessage(activeCategoryId)}
      </p>
    )
  }
  return (
    <LoadedRows
      // Each list loads from its own start.
      key={`${activeCategoryId}:${query}`}
      found={found}
      grouped={activeCategoryId === null}
    />
  )
}
