import { useState } from "react"

import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { ThoughtBubbleIcon } from "@/components/ui/icons"
import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

import { HINTED_ROW_CLASS, HintedLabel, MenuItemHint } from "./menu-item-hint"
import { readThinkingOn, writeThinkingOn } from "./thinking-preference"

/**
 * Whether the next answers think first. Read from storage when a message is
 * sent, so this only shows and changes the preference.
 */
export function ThinkingMenuItem({
  canSkip,
}: {
  // False for a model that cannot be told to stop: the switch stays on.
  canSkip: boolean
}) {
  const [stored, setStored] = useState(readThinkingOn)
  const on = stored || !canSkip
  const toggle = () => {
    writeThinkingOn(!on)
    setStored(!on)
  }

  const hint = !canSkip
    ? intl.formatMessage({
        id: "chat_composer_thinking_unavailable_tooltip",
        defaultMessage: "Only a local model can answer without thinking",
      })
    : on
      ? intl.formatMessage({
          id: "chat_composer_thinking_on_tooltip",
          defaultMessage: "Thinks before answering",
        })
      : intl.formatMessage({
          id: "chat_composer_thinking_off_tooltip",
          defaultMessage: "Answers sooner, without thinking",
        })

  return (
    <MenuItemHint hint={hint}>
      {/* Stays open on click, so the switch is seen to move. */}
      <DropdownMenuItem
        role="menuitemcheckbox"
        aria-checked={on}
        closeOnClick={false}
        disabled={!canSkip}
        className={HINTED_ROW_CLASS}
        onClick={toggle}
      >
        <ThoughtBubbleIcon />
        <HintedLabel
          label={intl.formatMessage({
            id: "chat_composer_thinking_label",
            defaultMessage: "Thinking",
          })}
          hint={hint}
        />
        {/* Drawn only: the row is the control, and a second one would nest. */}
        <Switch
          size="sm"
          checked={on}
          tabIndex={-1}
          aria-hidden
          className="pointer-events-none"
        />
      </DropdownMenuItem>
    </MenuItemHint>
  )
}
