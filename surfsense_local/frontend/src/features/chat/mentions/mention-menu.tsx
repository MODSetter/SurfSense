import {
  ComposerPrimitive,
  unstable_useTriggerPopoverScopeContext,
  type Unstable_TriggerItem,
} from "@assistant-ui/react"
import { useEffect } from "react"

import { Button } from "@/components/ui/button"
import {
  AiSparklesIcon,
  ArrowLeftIcon,
  ChevronRightIcon,
  Folder01Icon,
} from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { mentionGroupLabel } from "./mention-group-label"
import { mentionsOfGroup } from "./mention-items"
import { MentionItem, MentionItemDescription } from "./mention-list"

/** What `@` shows first: the groups, each with how many it holds. */
export function MentionGroups({
  items,
  isLoading,
}: {
  items: readonly Unstable_TriggerItem[]
  isLoading: boolean
}) {
  return (
    <ComposerPrimitive.Unstable_TriggerPopoverCategories>
      {(groups) =>
        groups.map(({ id, label }) => {
          const Icon = id === "artifact" ? AiSparklesIcon : Folder01Icon
          return (
            <MentionItem
              key={id}
              render={
                <ComposerPrimitive.Unstable_TriggerPopoverCategoryItem
                  categoryId={id}
                />
              }
              className="hover:bg-accent data-[highlighted]:bg-accent"
            >
              <Icon className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 truncate">{label}</span>
              {isLoading ? null : (
                <MentionItemDescription className="tabular-nums">
                  {intl.formatNumber(mentionsOfGroup(items, id).length)}
                </MentionItemDescription>
              )}
              <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" />
            </MentionItem>
          )
        })
      }
    </ComposerPrimitive.Unstable_TriggerPopoverCategories>
  )
}

/** Above an opened group: its name, and the way back to the groups. */
export function MentionGroupHeader() {
  const { activeCategoryId, isSearchMode, open } =
    unstable_useTriggerPopoverScopeContext()
  if (!open || !activeCategoryId || isSearchMode) return null
  return (
    <div className="sticky -top-1 z-10 -mx-1 -mt-1 mb-0.5 flex items-center gap-1 bg-popover px-1 pt-1 text-xs text-muted-foreground select-none">
      <ComposerPrimitive.Unstable_TriggerPopoverBack asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={intl.formatMessage({
            id: "chat_mentions_back_aria",
            defaultMessage: "Back",
          })}
          onMouseDown={(event) => event.preventDefault()}
        >
          <ArrowLeftIcon />
        </Button>
      </ComposerPrimitive.Unstable_TriggerPopoverBack>
      <span>{mentionGroupLabel(activeCategoryId)}</span>
    </div>
  )
}

/** Typing inside a group searches both: the popover's own filter inside one would
 *  match ids and details as well as names. */
export function SearchLeavesTheGroup() {
  const { activeCategoryId, query, goBack } =
    unstable_useTriggerPopoverScopeContext()
  useEffect(() => {
    if (activeCategoryId && query) goBack()
  }, [activeCategoryId, goBack, query])
  return null
}
