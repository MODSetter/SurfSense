import { Fragment } from "react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { BotIcon, Chat01Icon, ChevronDownIcon } from "@/components/ui/icons"
import { Badge } from "@/components/ui/badge"
import type { ChatMode, ChatModes } from "@/features/models/capability/api"
import type { ModelSelection } from "@/features/models/selection/api"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { HINTED_ROW_CLASS, MenuItemHint } from "../menu-item-hint"
import { modelControlButtonClassName } from "../model-picker"
import {
  agenticBlockedText,
  agenticReasonTag,
  agenticReasonText,
  modeLabel,
  modeShortDescription,
} from "./mode-text"
import {
  useChatModes,
  useNewChatMode,
  usePickNewChatMode,
} from "./new-chat-mode"

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
  const modes = useChatModes(model)
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
            <ModeList
              modes={modes}
              value={newChatMode}
              onPick={(mode) => pick(model, mode)}
            />
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

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
            {intl.formatMessage({
              id: "chat_mode_picker_open_chat_label",
              defaultMessage: "This chat’s mode",
            })}
          </DropdownMenuLabel>
          <ModeList
            modes={modes}
            value={threadMode}
            // A chat keeps its mode, so the other one opens a new chat.
            onPick={(mode) => {
              if (mode === threadMode) return
              pick(model, mode)
              onNewChat?.()
            }}
            otherOpensNewChat
          />
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Basic and Agentic as radio rows, the same in a new chat and an open one. */
function ModeList({
  modes,
  value,
  onPick,
  otherOpensNewChat = false,
}: {
  modes: ChatModes
  value: ChatMode
  onPick: (mode: ChatMode) => void
  otherOpensNewChat?: boolean
}) {
  return (
    <DropdownMenuRadioGroup
      value={value}
      onValueChange={(next) => onPick(next as ChatMode)}
    >
      {(["basic", "agentic"] as const).map((mode) => {
        // Agentic's score or gate, said beside the menu as the add menu says
        // why a row is held.
        const hint = mode === "agentic" ? agenticNote(modes) : null
        const opensNewChat = otherOpensNewChat && mode !== value
        const item = (
          <DropdownMenuRadioItem
            value={mode}
            closeOnClick
            disabled={mode === "agentic" && !modes.agentic_allowed}
            className={cn(
              "items-start",
              HINTED_ROW_CLASS,
              opensNewChat && "pr-2"
            )}
          >
            <ModeRow
              mode={mode}
              label={modeLabel(mode)}
              detail={modeShortDescription(mode)}
              tag={
                mode === "agentic" && modes.agentic_allowed
                  ? agenticReasonTag(modes.reason)
                  : null
              }
              hint={hint}
            />
            {opensNewChat ? (
              <span className="shrink-0 text-xs text-muted-foreground">
                {intl.formatMessage({
                  id: "chat_mode_picker_opens_new_chat_label",
                  defaultMessage: "New chat",
                })}
              </span>
            ) : null}
          </DropdownMenuRadioItem>
        )
        return hint ? (
          <MenuItemHint key={mode} hint={hint}>
            {item}
          </MenuItemHint>
        ) : (
          <Fragment key={mode}>{item}</Fragment>
        )
      })}
    </DropdownMenuRadioGroup>
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
  label,
  detail,
  tag,
  hint,
}: {
  mode: ChatMode
  label: string
  detail: string
  tag?: string | null
  // The row's tooltip, which screen readers cannot see.
  hint?: string | null
}) {
  const Icon = MODE_ICON[mode]
  return (
    <>
      <Icon className="mt-0.5" />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-1.5">
          <span>{label}</span>
          {tag ? (
            <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">
              {tag}
            </Badge>
          ) : null}
        </span>
        <span className="text-xs text-muted-foreground">{detail}</span>
        {hint ? <span className="sr-only">{hint}</span> : null}
      </span>
    </>
  )
}
