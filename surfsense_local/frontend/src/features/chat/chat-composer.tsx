import { type ReactNode } from "react"
import { ComposerPrimitive, useAuiState } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { ArrowUp02Icon, CircleStopIcon } from "@/components/ui/icons"
import type { ModelSelection } from "@/features/models/selection/api"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { ComposerImage } from "./attached-image"
import { ComposerAddMenu } from "./composer-add-menu"
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
    <button
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
    </button>
  )
}

function ComposerAction({
  isRunning,
  className,
}: {
  isRunning: boolean
  className?: string
}) {
  if (!isRunning) {
    return (
      <ComposerPrimitive.Send asChild>
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
  // Attach and paste take images only while the selected model reads them.
  readsImages: boolean
  // The conversation the composer writes into, named for a screen reader.
  describedBy?: string
  onUploadSources?: (files: File[]) => void
  isUploadingSources?: boolean
}) {
  // Said only once the cap is reached: that is the moment typing, or the tail
  // of a paste, stops landing, and the one moment it needs explaining.
  const atLimit = useAuiState(
    ({ composer }) => composer.text.length >= QUESTION_MAX_CHARS
  )
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
      thinking={model ? { canSkip: canSkipThinking(model) } : undefined}
      onUploadSources={onUploadSources}
      isUploadingSources={isUploadingSources}
      className={className}
    />
  )
  return (
    <div
      className="relative mx-auto w-full max-w-xl"
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
          "relative rounded-2xl border bg-card p-1.5 shadow-sm transition-colors focus-within:border-ring/40 hover:border-ring/40",
          placement === "bottom" && "flex items-end gap-2"
        )}
      >
        {placement === "bottom" ? addMenu("-mr-1.5 mb-0.5") : null}
        <ComposerPrimitive.Input
          autoFocus
          unstable_focusOnThreadSwitched
          aria-describedby={describedBy}
          // Held whenever a send could not go anywhere: no model, a model that
          // can't be used, or egress to it still off.
          disabled={
            !model || !providerAvailable || blockedPlaceholder !== undefined
          }
          className={cn(
            "max-h-44 resize-none bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-muted-foreground",
            placement === "center"
              ? "block min-h-20 w-full pb-12"
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
          addAttachmentOnPaste={readsImages}
          rows={1}
          maxLength={QUESTION_MAX_CHARS}
          aria-label={intl.formatMessage({
            id: "chat_composer_message_aria",
            defaultMessage: "Message",
          })}
        />
        {placement === "center" ? (
          <>
            {addMenu("absolute bottom-2 left-1.5")}
            <div className="absolute right-1.5 bottom-2 flex items-center gap-2">
              <SourceCount count={sourceCount} />
              <ModelControl
                model={model}
                onModelSetup={onModelSetup}
                onModelSelected={onModelSelected}
              />
              <ComposerAction isRunning={isRunning} />
            </div>
          </>
        ) : (
          <>
            <SourceCount count={sourceCount} className="mb-2" />
            <ComposerAction isRunning={isRunning} className="mb-0.5" />
          </>
        )}
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
          {/* Keeps its line and leaves the model name what is left, never less
          than 7rem, so a long translation truncates the name before wrapping. */}
          <p className="max-w-[calc(100%-7rem)] shrink-0 text-left text-[11px] text-muted-foreground select-none">
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
          <div className="flex min-w-0 items-center gap-1">
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
