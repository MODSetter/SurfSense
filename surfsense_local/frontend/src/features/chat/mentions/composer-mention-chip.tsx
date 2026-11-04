import type { DirectiveChipProps } from "@assistant-ui/react-lexical"

import { MentionIcon } from "./mention-icon"

/** A named source in the message box: one unit, deleted whole. */
export function ComposerMentionChip({
  directiveId,
  directiveType,
  label,
}: DirectiveChipProps) {
  return (
    <span className="inline-flex max-w-full items-baseline gap-1 rounded-md px-0.5 align-baseline font-medium text-notice transition-colors select-none hover:bg-notice/10 motion-reduce:transition-none">
      <MentionIcon
        id={directiveId}
        type={directiveType}
        className="size-3.5 shrink-0 self-center"
      />
      <span className="max-w-64 truncate">{label}</span>
    </span>
  )
}
