import {
  ComposerPrimitive,
  defaultDirectiveFormatter,
  type TriggerAdapter,
} from "@assistant-ui/react"
import { useMemo } from "react"

import { ScrollFade } from "@/components/ui/scroll-fade"

import { keepHighlightedRowInView } from "./keep-highlighted-row-in-view"
import { mentionGroupLabel } from "./mention-group-label"
import {
  MENTION_GROUPS,
  mentionItems,
  mentionsOfGroup,
  searchMentions,
  type Mentionables,
} from "./mention-items"
import { MentionList } from "./mention-list"
import { MentionListAtCaret } from "./mention-list-at-caret"
import { MENTION_TRIGGER, mentionAmongNames } from "./mention-matcher"
import {
  MentionGroupHeader,
  MentionGroups,
  SearchLeavesTheGroup,
} from "./mention-menu"
import { MentionRows } from "./mention-rows"

/** Typing `@` in an Agentic composer offers Sources and Artifacts to name for the
 *  agent, which may read them whatever is ticked; typing a name searches both. */
export function SourceMentions({
  mentionables,
}: {
  mentionables?: Mentionables
}) {
  const isLoading = mentionables?.isLoading ?? false
  const items = useMemo(
    () => (mentionables ? mentionItems(mentionables) : []),
    [mentionables]
  )
  const adapter = useMemo<TriggerAdapter>(
    () => ({
      categories: () =>
        MENTION_GROUPS.map((id) => ({ id, label: mentionGroupLabel(id) })),
      categoryItems: (group) => mentionsOfGroup(items, group),
      search: (query) => searchMentions(items, query),
    }),
    [items]
  )

  const matcher = useMemo(
    () => mentionAmongNames(items.map((item) => item.label)),
    [items]
  )

  return (
    // The popover puts its parts in the composer's layout while closed, and a thread's
    // composer is a row with a gap. Out of flow, none of them can move what is in it.
    <div
      data-mention-layer
      className="pointer-events-none absolute inset-0 *:pointer-events-auto"
    >
      <MentionList
        render={
          <ComposerPrimitive.TriggerPopover
            char={MENTION_TRIGGER}
            adapter={adapter}
            matcher={matcher}
          />
        }
      >
        <ComposerPrimitive.TriggerPopover.Directive
          formatter={defaultDirectiveFormatter}
        />
        <MentionListAtCaret />
        <SearchLeavesTheGroup />
        <MentionGroups items={items} isLoading={isLoading} />
        <MentionGroupHeader />
        {/* The rows alone scroll and fade, under a header that stays clear. */}
        <ScrollFade className="flex flex-col" viewportClassName="h-auto">
          <ComposerPrimitive.TriggerPopoverItems ref={keepHighlightedRowInView}>
            {(found) => <MentionRows found={found} isLoading={isLoading} />}
          </ComposerPrimitive.TriggerPopoverItems>
        </ScrollFade>
      </MentionList>
    </div>
  )
}
