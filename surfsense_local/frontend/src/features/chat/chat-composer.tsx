import { type MouseEvent, type ReactNode } from "react"
import { ComposerPrimitive, useAuiState } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { ArrowUp02Icon, CircleStopIcon } from "@/components/ui/icons"
import type { Dictation } from "@/features/dictation/dictation-adapter"
import { MicButton } from "@/features/dictation/mic/mic-button"
import { DictationStrip } from "@/features/dictation/strip/dictation-strip"
import { useDictationKeys } from "@/features/dictation/use-dictation-keys"
import { useDictationStripShown } from "@/features/dictation/use-dictation-view"
import type { ChatMode } from "@/features/models/capability/api"
import type { ModelSelection } from "@/features/models/selection/api"
import { PluginMentions } from "@/features/plugins/in-thread/plugin-mentions"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"
import type { PluginsStart } from "@/features/plugins/plugins-settings"

import { ComposerImage } from "./attached-image"
import { ComposerAddMenu } from "./composer-add-menu"
import { ModePicker } from "./modes/mode-picker"
import { useNewChatMode } from "./modes/new-chat-mode"
import { ModelPicker, modelControlButtonClassName } from "./model-picker"
import { QUESTION_MAX_CHARS } from "./question-limit"
import { canSkipThinking } from "./thinking-preference"

function ModelControl({
  model,
  onModelSelected,
  onModelSetup,
  className,
}: {
  model: ModelSelection | null
  onModelSelected: (selection: ModelSelection) => void
  onModelSetup: () => void
  className?: string
}) {
  return model ? (
    <ModelPicker
      model={model}
      onManageModels={onModelSetup}
      onModelSelected={onModelSelected}
      className={className}
    />
  ) : (
    <Button
      variant="bare"
      type="button"
      className={cn(
        modelControlButtonClassName,
        "text-white hover:text-white",
        className
      )}
      onClick={onModelSetup}
    >
      {intl.formatMessage({
        id: "chat_composer_set_up_model_button",
        defaultMessage: "Set up model",
      })}
    </Button>
  )
}

function ComposerAction({
  isRunning,
  onSendClick,
  className,
}: {
  isRunning: boolean
  // Prevented while voice input runs, which Send then stops instead.
  onSendClick?: (event: MouseEvent<HTMLButtonElement>) => void
  className?: string
}) {
  if (!isRunning) {
    return (
      <ComposerPrimitive.Send asChild onClick={onSendClick}>
        <Button
          size="icon-lg"
          className={cn("rounded-xl", className)}
          aria-label={intl.formatMessage({
            id: "chat_composer_send_aria",
            defaultMessage: "Send message",
          })}
        >
          <ArrowUp02Icon />
        </Button>
      </ComposerPrimitive.Send>
    )
  }

  return (
    <ComposerPrimitive.Cancel asChild>
      <Button
        size="icon-lg"
        variant="secondary"
        className={cn("rounded-xl", className)}
        aria-label={intl.formatMessage({
          id: "chat_composer_stop_aria",
          defaultMessage: "Stop generating",
        })}
      >
        <CircleStopIcon />
      </Button>
    </ComposerPrimitive.Cancel>
  )
}

function SourceCount({
  count,
  className,
}: {
  count: number
  className?: string
}) {
  const label = intl.formatMessage(
    {
      id: "chat_composer_source_count_label",
      defaultMessage: "{count, plural, one {# source} other {# sources}}",
    },
    { count }
  )
  return (
    <span
      className={cn(
        "px-1.5 py-1 text-[11px] font-normal text-muted-foreground tabular-nums select-none",
        className
      )}
    >
      {label}
    </span>
  )
}

export function ChatComposer({
  placement,
  model,
  sourceCount,
  isRunning,
  providerAvailable,
  notice,
  blockedPlaceholder,
  onModelSetup,
  onModelSelected,
  readsImages,
  describedBy,
  onUploadSources,
  isUploadingSources = false,
  threadMode = null,
  onNewChat,
  onOpenPlugins,
  dictation,
  onOpenSpeechSettings,
}: {
  placement: "center" | "bottom"
  model: ModelSelection | null
  sourceCount: number
  isRunning: boolean
  providerAvailable: boolean
  // Above the composer: why the saved model could not be used at startup.
  notice?: ReactNode
  // Set while something outside the model holds sending, such as egress.
  blockedPlaceholder?: string
  onModelSetup: () => void
  onModelSelected: (selection: ModelSelection) => void
  // Attach and paste take images only while the selected model reads them,
  // and the chat is not Agentic.
  readsImages: boolean
  // The conversation the composer writes into, named for a screen reader.
  describedBy?: string
  onUploadSources?: (files: File[]) => void
  isUploadingSources?: boolean
  // The open chat's mode, which it keeps; null for a new chat or one being made.
  threadMode?: ChatMode | null
  // Starts a new chat, for an open chat's offer of the other mode.
  onNewChat?: () => void
  // Opens Settings › Plugins, from the add menu's plugins.
  onOpenPlugins?: (start?: PluginsStart) => void
  // Voice input; absent, the composer has no mic.
  dictation?: Dictation
  // Opens Settings › Speech recognition, from the mic's set-up.
  onOpenSpeechSettings?: () => void
}) {
  const newChatMode = useNewChatMode(model)
  // The agent reads no attached images yet: an Agentic chat takes none. Images
  // already attached stay in view, so they can be removed.
  const agentic = (threadMode ?? newChatMode) === "agentic"
  // Said only once the cap is reached: that is the moment typing, or the tail
  // of a paste, stops landing, and the one moment it needs explaining.
  const atLimit = useAuiState(
    ({ composer }) => composer.text.length >= QUESTION_MAX_CHARS
  )
  const dictationKeys = useDictationKeys(dictation)
  const stripShown = useDictationStripShown(dictation)
  const inputDisabled =
    !model || !providerAvailable || blockedPlaceholder !== undefined
  const mic = (className: string) =>
    dictation ? (
      <MicButton
        dictation={dictation}
        disabled={inputDisabled || atLimit}
        onOpenSpeechSettings={onOpenSpeechSettings}
        className={className}
      />
    ) : null
  const strip = (className: string) =>
    dictation ? (
      <DictationStrip
        dictation={dictation}
        onOpenSpeechSettings={onOpenSpeechSettings}
        className={className}
      />
    ) : null
  const limitNotice = atLimit
    ? intl.formatMessage(
        {
          id: "chat_composer_length_limit_status",
          defaultMessage: "Messages are limited to {max, number} characters.",
        },
        { max: QUESTION_MAX_CHARS }
      )
    : null
  const addMenu = (className: string) => (
    <ComposerAddMenu
      readsImages={readsImages}
      agentic={agentic}
      // The agent never reads the switch, open chat or new, so it is not offered.
      thinking={
        model && !agentic ? { canSkip: canSkipThinking(model) } : undefined
      }
      onUploadSources={onUploadSources}
      isUploadingSources={isUploadingSources}
      onManagePlugins={onOpenPlugins}
      className={className}
    />
  )
  return (
    <div
      className="relative mx-auto w-full max-w-2xl"
      data-composer-placement={placement}
    >
      {notice ? (
        // Tucked behind the composer, which paints over its lower edge: out of
        // flow, so the composer keeps its place and its own shape.
        <div className="absolute inset-x-0 bottom-full -mb-4">{notice}</div>
      ) : null}
      {readsImages ? (
        <div className="mb-2 flex flex-wrap gap-2 px-1 empty:hidden">
          <ComposerPrimitive.Attachments
            components={{ Image: ComposerImage, Attachment: ComposerImage }}
          />
        </div>
      ) : null}
      <ComposerPrimitive.Root
        className={cn(
          // No top padding: the text scrolls up to the border, not to a strip
          // above it, and holds that space in its own padding instead.
          "relative rounded-2xl border bg-card px-1.5 pb-1.5 shadow-sm transition-colors focus-within:border-ring/40 hover:border-ring/40",
          placement === "bottom" && "flex items-end gap-2"
        )}
      >
        <ComposerPrimitive.Unstable_TriggerPopoverRoot>
          {/* Plugins reach Agentic threads only, so only their composer names tools. */}
          {agentic ? <PluginMentions /> : null}
          {placement === "bottom" ? addMenu("-mr-1.5 mb-0.5") : null}
          <ComposerPrimitive.Input
            autoFocus
            unstable_focusOnThreadSwitched
            aria-describedby={describedBy}
            // Held whenever a send could not go anywhere: no model, a model that
            // can't be used, or egress to it still off.
            disabled={inputDisabled}
            // Voice input writes the text meanwhile; the box keeps its focus and keys.
            readOnly={dictationKeys.recording}
            cancelOnEscape={!dictationKeys.recording}
            onKeyDown={dictationKeys.onKeyDown}
            className={cn(
              "max-h-44 resize-none bg-transparent px-2 pt-4 pb-2.5 text-sm outline-none placeholder:text-muted-foreground",
              placement === "center"
                ? "block min-h-12 w-full"
                : "min-h-10 flex-1"
            )}
            placeholder={
              blockedPlaceholder !== undefined
                ? blockedPlaceholder
                : !model || providerAvailable
                  ? placement === "center"
                    ? intl.formatMessage({
                        id: "chat_composer_start_placeholder",
                        defaultMessage: "Turn your sources into answers",
                      })
                    : intl.formatMessage({
                        id: "chat_composer_follow_up_placeholder",
                        defaultMessage: "Follow up on this answer",
                      })
                  : intl.formatMessage({
                      id: "chat_composer_provider_offline_placeholder",
                      defaultMessage: "Reconnect your model provider to send",
                    })
            }
            submitMode="enter"
            addAttachmentOnPaste={readsImages && !agentic}
            rows={1}
            maxLength={QUESTION_MAX_CHARS}
            aria-label={intl.formatMessage({
              id: "chat_composer_message_aria",
              defaultMessage: "Message",
            })}
          />
          {placement === "center" ? (
            // Its own row under the text, never over it: long text scrolls
            // inside the box and stops above the controls.
            <div className="flex items-center justify-between gap-2">
              <div className="flex shrink-0 items-center gap-1">
                {addMenu("")}
                {model ? <ModePicker model={model} threadMode={null} /> : null}
              </div>
              <div className="flex min-w-0 items-center gap-2">
                {stripShown ? (
                  strip("max-w-56")
                ) : (
                  <>
                    <SourceCount count={sourceCount} />
                    <ModelControl
                      model={model}
                      onModelSetup={onModelSetup}
                      onModelSelected={onModelSelected}
                    />
                  </>
                )}
                {mic("")}
                <ComposerAction
                  isRunning={isRunning}
                  onSendClick={dictationKeys.onSendClick}
                />
              </div>
            </div>
          ) : (
            <>
              <SourceCount count={sourceCount} className="mb-2" />
              {mic("-mr-1 mb-0.5")}
              <ComposerAction
                isRunning={isRunning}
                onSendClick={dictationKeys.onSendClick}
                className="mb-0.5"
              />
            </>
          )}
        </ComposerPrimitive.Unstable_TriggerPopoverRoot>
      </ComposerPrimitive.Root>
      {placement === "center" && limitNotice ? (
        <p
          role="status"
          className="mt-1 px-2 text-[11px] text-muted-foreground select-none"
        >
          {limitNotice}
        </p>
      ) : null}
      {placement === "bottom" ? (
        <div className="mt-1 flex min-h-7 items-center justify-between gap-3 px-2">
          {/* Keeps its line and leaves the mode and the model name what is
          left, never less than 13rem, so a long translation truncates the
          name before wrapping. */}
          {stripShown ? (
            strip("max-w-[calc(100%-13rem)] min-h-7 flex-1")
          ) : (
            <p className="max-w-[calc(100%-13rem)] shrink-0 text-left text-[11px] text-muted-foreground select-none">
              {limitNotice ? (
                <span role="status">{limitNotice}</span>
              ) : !model || providerAvailable ? (
                intl.formatMessage({
                  id: "chat_composer_disclaimer_body",
                  defaultMessage:
                    "SurfSense can make mistakes. Check important answers.",
                })
              ) : (
                intl.formatMessage({
                  id: "chat_composer_provider_offline_body",
                  defaultMessage:
                    "Historical chats remain available while the provider is offline.",
                })
              )}
            </p>
          )}
          <div className="flex min-w-0 items-center gap-1">
            {model && threadMode !== null ? (
              <ModePicker
                model={model}
                threadMode={threadMode}
                onNewChat={onNewChat}
              />
            ) : null}
            <ModelControl
              model={model}
              onModelSetup={onModelSetup}
              onModelSelected={onModelSelected}
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}
