import { FileTextIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"

import type { TurnSources } from "./api"

// Past this many, names would crowd the line: it counts them and names them on hover.
const NAMED_INLINE = 3

const LINE_CLASS =
  "flex max-w-[78%] items-start gap-1.5 text-xs leading-5 text-muted-foreground"

function countLabel(count: number) {
  return intl.formatMessage(
    {
      id: "agent_scope_count_label",
      defaultMessage:
        "Working from {count, plural, one {# source} other {# sources}}",
    },
    { count }
  )
}

/** Which sources an agent turn was allowed to use; nothing when it named no selection. */
export function WorkingFrom({ scope }: { scope: TurnSources | null }) {
  if (scope === null) return null
  const { titles } = scope
  const icon = <FileTextIcon className="mt-0.5 size-3.5 shrink-0" />

  // Too many to tag one by one: the server sent only how many.
  if (scope.count !== undefined && titles.length === 0) {
    return (
      <p className={LINE_CLASS}>
        {icon}
        <span>{countLabel(scope.count)}</span>
      </p>
    )
  }

  if (titles.length === 0) {
    return (
      <p className={LINE_CLASS}>
        {icon}
        <span>
          {intl.formatMessage({
            id: "agent_scope_none_label",
            defaultMessage: "Working from no sources",
          })}
        </span>
      </p>
    )
  }

  const names = intl.formatList(titles, { type: "conjunction" })
  if (titles.length <= NAMED_INLINE) {
    return (
      <p className={LINE_CLASS}>
        {icon}
        <span className="min-w-0 break-words">
          {intl.formatMessage(
            {
              id: "agent_scope_named_label",
              defaultMessage: "Working from {names}",
            },
            { names }
          )}
        </span>
      </p>
    )
  }

  return (
    <p className={LINE_CLASS}>
      {icon}
      <Tooltip>
        <TooltipTrigger
          render={
            <span
              className="cursor-default rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              tabIndex={0}
            />
          }
        >
          {countLabel(titles.length)}
        </TooltipTrigger>
        <TooltipContent className="max-w-80">{names}</TooltipContent>
      </Tooltip>
    </p>
  )
}
