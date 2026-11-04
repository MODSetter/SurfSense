import {
  ComposerPrimitive,
  useAui,
  type DirectiveFormatter,
  type TriggerAdapter,
} from "@assistant-ui/react"
import { useMemo } from "react"

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
import { MENTION_TRIGGER, mentionAt } from "./mention-matcher"
import {
  MentionGroupHeader,
  MentionGroups,
  SearchLeavesTheGroup,
} from "./mention-menu"
import { MentionRows } from "./mention-rows"
import { withPick } from "./named-sources"

// The name as the user knows it: the composer is a textarea, so anything else
// would show as written. The id goes beside the text, in the run's config.
const formatter: DirectiveFormatter = {
  serialize: (item) => `${MENTION_TRIGGER}${item.label}`,
  parse: (text) => [{ kind: "text", text }],
}

/** Typing `@` in an Agentic composer offers Sources and Artifacts to name for the
 *  agent, which may read them whatever is ticked; typing a name searches both. */
export function SourceMentions({
  mentionables,
}: {
  mentionables?: Mentionables
}) {
  const aui = useAui()
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

  return (
    <MentionList
      render={
        <ComposerPrimitive.TriggerPopover
          char={MENTION_TRIGGER}
          adapter={adapter}
          // The rule the startup frame's box uses too.
          matcher={mentionAt}
        />
      }
    >
      <ComposerPrimitive.TriggerPopover.Directive
        formatter={formatter}
        onInserted={({ id, label }) => {
          const composer = aui.composer()
          composer.setRunConfig(
            withPick(composer.getState().runConfig, { id, label })
          )
        }}
      />
      <SearchLeavesTheGroup />
      <MentionGroups items={items} isLoading={isLoading} />
      <MentionGroupHeader />
      <ComposerPrimitive.TriggerPopoverItems ref={keepHighlightedRowInView}>
        {(found) => <MentionRows found={found} isLoading={isLoading} />}
      </ComposerPrimitive.TriggerPopoverItems>
    </MentionList>
  )
}
