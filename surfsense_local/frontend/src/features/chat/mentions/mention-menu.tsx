import { ComposerPrimitive, type TriggerItem } from "@assistant-ui/react"
import { useEffect } from "react"

import { Button } from "@/components/ui/button"
import {
  ArrowLeftIcon,
  ChevronRightIcon,
  LibraryBigIcon,
  Shapes01Icon,
} from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { mentionGroupLabel } from "./mention-group-label"
import { mentionsOfGroup } from "./mention-items"
import { useMentionPopoverScope } from "./mention-popover-scope"
import { MentionItemDescription, MentionRowButton } from "./mention-list"

/** What `@` shows first: the groups, each with how many it holds. */
export function MentionGroups({
  items,
  isLoading,
}: {
  items: readonly TriggerItem[]
  isLoading: boolean
}) {
  return (
    <ComposerPrimitive.TriggerPopoverCategories>
      {(groups) =>
        groups.map(({ id, label }) => {
          const Icon = id === "artifact" ? Shapes01Icon : LibraryBigIcon
          return (
            <ComposerPrimitive.TriggerPopoverCategoryItem
              key={id}
              categoryId={id}
              asChild
            >
              <MentionRowButton>
                <Icon className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 truncate">{label}</span>
                {isLoading ? null : (
                  <MentionItemDescription className="tabular-nums">
                    {intl.formatNumber(mentionsOfGroup(items, id).length)}
                  </MentionItemDescription>
                )}
                <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" />
              </MentionRowButton>
            </ComposerPrimitive.TriggerPopoverCategoryItem>
          )
        })
      }
    </ComposerPrimitive.TriggerPopoverCategories>
  )
}

/** Above an opened group: its name, and the way back to the groups. */
export function MentionGroupHeader() {
  const { activeCategoryId, isSearchMode, open } = useMentionPopoverScope()
  if (!open || !activeCategoryId || isSearchMode) return null
  const group = mentionGroupLabel(activeCategoryId)
  return (
    <div className="mb-0.5 shrink-0">
      <ComposerPrimitive.TriggerPopoverBack asChild>
        <Button
          static
          variant="ghost"
          size="sm"
          // Names what it shows, for a screen reader and for speech control.
          aria-label={intl.formatMessage(
            {
              id: "chat_mentions_back_aria",
              defaultMessage: "Back from {group}",
            },
            { group }
          )}
          onMouseDown={(event) => event.preventDefault()}
          className="w-full justify-start px-1.5 text-xs font-normal text-muted-foreground"
        >
          <ArrowLeftIcon />
          {group}
        </Button>
      </ComposerPrimitive.TriggerPopoverBack>
    </div>
  )
}

/** Typing inside a group searches both: the popover's own filter inside one would
 *  match ids and details as well as names. */
export function SearchLeavesTheGroup() {
  const { activeCategoryId, query, goBack } = useMentionPopoverScope()
  useEffect(() => {
    if (activeCategoryId && query) goBack()
  }, [activeCategoryId, goBack, query])
  return null
}
