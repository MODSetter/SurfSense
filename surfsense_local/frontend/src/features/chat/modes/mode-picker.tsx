import type { ReactNode } from "react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  BotIcon,
  Chat01Icon,
  ChevronDownIcon,
  PlusIcon,
} from "@/components/ui/icons"
import type { ChatMode, ChatModes } from "@/features/models/capability/api"
import type { ModelSelection } from "@/features/models/selection/api"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { HINTED_ROW_CLASS } from "../menu-item-hint"
import { modelControlButtonClassName } from "../model-picker"
import {
  agenticBlockedText,
  agenticReasonText,
  modeDescription,
  modeLabel,
} from "./mode-text"
import { useNewChatMode, usePickNewChatMode } from "./new-chat-mode"

const MODE_ICON = { basic: Chat01Icon, agentic: BotIcon } as const

/**
 * The composer's Basic (Q&A) / Agentic switch. A new chat picks its mode
 * here; an open chat shows the mode it keeps, and offers the other one only
 * as a new chat.
 */
export function ModePicker({
  model,
  threadMode,
  onNewChat,
  className,
}: {
  model: ModelSelection
  // The open chat's mode, which it keeps; null for a new chat.
  threadMode: ChatMode | null
  onNewChat?: () => void
  className?: string
}) {
  const newChatMode = useNewChatMode(model)
  const pick = usePickNewChatMode()
  const modes = model.capability?.modes
  if (!modes || !newChatMode) return null

  if (threadMode === null) {
    return (
      <DropdownMenu>
        <ModeTrigger
          mode={newChatMode}
          className={className}
          ariaLabel={intl.formatMessage(
            {
              id: "chat_mode_picker_trigger_aria",
              defaultMessage: "Chat mode {mode}. Change mode.",
            },
            { mode: modeLabel(newChatMode) }
          )}
        />
        <DropdownMenuContent align="start" className="w-72">
          <DropdownMenuGroup>
            <DropdownMenuLabel>
              {intl.formatMessage({
                id: "chat_mode_picker_new_chat_label",
                defaultMessage: "Mode for this chat",
              })}
            </DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={newChatMode}
              onValueChange={(next) => pick(model, next as ChatMode)}
            >
              {(["basic", "agentic"] as const).map((mode) => (
                <DropdownMenuRadioItem
                  key={mode}
                  value={mode}
                  closeOnClick
                  disabled={mode === "agentic" && !modes.agentic_allowed}
                  className={cn("items-start", HINTED_ROW_CLASS)}
                >
                  <ModeRow
                    mode={mode}
                    label={modeLabel(mode)}
                    detail={modeDescription(mode)}
                    note={mode === "agentic" ? agenticNote(modes) : null}
                  />
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  const other: ChatMode = threadMode === "agentic" ? "basic" : "agentic"
  const otherBlocked = other === "agentic" && !modes.agentic_allowed
  return (
    <DropdownMenu>
      <ModeTrigger
        mode={threadMode}
        className={className}
        ariaLabel={intl.formatMessage(
          {
            id: "chat_mode_picker_thread_aria",
            defaultMessage:
              "Chat mode {mode}. A chat keeps its mode; start a new chat for another.",
          },
          { mode: modeLabel(threadMode) }
        )}
      />
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            {intl.formatMessage(
              {
                id: "chat_mode_picker_kept_label",
                defaultMessage:
                  "{mode, select, agentic {This chat runs in Agentic mode} other {This chat runs in Basic (Q&A) mode}}",
              },
              { mode: threadMode }
            )}
          </DropdownMenuLabel>
          <DropdownMenuItem
            disabled={otherBlocked}
            className={cn("items-start", HINTED_ROW_CLASS)}
            onClick={() => {
              pick(model, other)
              onNewChat?.()
            }}
          >
            <ModeRow
              mode={other}
              icon={<PlusIcon className="mt-0.5" />}
              label={intl.formatMessage(
                {
                  id: "chat_mode_picker_start_new_label",
                  defaultMessage:
                    "{mode, select, agentic {Start a new chat in Agentic mode} other {Start a new chat in Basic (Q&A) mode}}",
                },
                { mode: other }
              )}
              detail={modeDescription(other)}
              note={other === "agentic" ? agenticNote(modes) : null}
            />
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Beside Agentic: why it cannot be picked, else its score or warning. */
function agenticNote(modes: ChatModes) {
  return modes.agentic_allowed
    ? agenticReasonText(modes.reason)
    : agenticBlockedText(modes.blocked ?? "")
}

function ModeTrigger({
  mode,
  ariaLabel,
  className,
}: {
  mode: ChatMode
  ariaLabel: string
  className?: string
}) {
  const Icon = MODE_ICON[mode]
  return (
    <DropdownMenuTrigger
      render={
        <button
          type="button"
          className={cn(modelControlButtonClassName, className)}
          title={intl.formatMessage({
            id: "chat_mode_picker_change_tooltip",
            defaultMessage: "Basic (Q&A) or Agentic",
          })}
          aria-label={ariaLabel}
        >
          <Icon className="size-3.5" />
          <span className="whitespace-nowrap">{modeLabel(mode)}</span>
          <ChevronDownIcon className="size-3" />
        </button>
      }
    />
  )
}

function ModeRow({
  mode,
  icon,
  label,
  detail,
  note,
}: {
  mode: ChatMode
  icon?: ReactNode
  label: string
  detail: string
  note: string | null
}) {
  const Icon = MODE_ICON[mode]
  return (
    <>
      {icon ?? <Icon className="mt-0.5" />}
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span>{label}</span>
        <span className="text-xs text-muted-foreground">{detail}</span>
        {note ? (
          <span className="text-xs text-muted-foreground">{note}</span>
        ) : null}
      </span>
    </>
  )
}
