import { useRef, type ChangeEvent } from "react"
import { ComposerPrimitive } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import { ArrowUp02Icon, CircleStopIcon, PlusIcon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { ModelSelection } from "@/features/models/selection/api"
import { SOURCE_FILE_ACCEPT } from "@/features/sources/api"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { ModelPicker, modelControlButtonClassName } from "./model-picker"

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

function AddSourcesButton({
  isUploading,
  onUpload,
  className,
}: {
  isUploading: boolean
  onUpload: (files: File[]) => void
  className?: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const upload = (event: ChangeEvent<HTMLInputElement>) => {
    onUpload(Array.from(event.target.files ?? []))
    event.target.value = ""
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={SOURCE_FILE_ACCEPT}
        className="sr-only"
        aria-label={intl.formatMessage({
          id: "chat_composer_add_files_aria",
          defaultMessage: "Add source files",
        })}
        disabled={isUploading}
        onChange={upload}
      />
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            size="icon-lg"
            variant="ghost"
            className={cn("rounded-xl", className)}
            disabled={isUploading}
            aria-label={intl.formatMessage({
              id: "chat_composer_add_sources_aria",
              defaultMessage: "Add sources",
            })}
            onClick={() => inputRef.current?.click()}
          >
            <PlusIcon className="size-5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">
          {intl.formatMessage({
            id: "chat_composer_add_sources_tooltip",
            defaultMessage: "Add sources",
          })}
        </TooltipContent>
      </Tooltip>
    </>
  )
}

export function ChatComposer({
  placement,
  model,
  sourceCount,
  isRunning,
  isUploading,
  providerAvailable,
  onModelSetup,
  onModelSelected,
  onUpload,
}: {
  placement: "center" | "bottom"
  model: ModelSelection | null
  sourceCount: number
  isRunning: boolean
  isUploading: boolean
  providerAvailable: boolean
  onModelSetup: () => void
  onModelSelected: (selection: ModelSelection) => void
  onUpload: (files: File[]) => void
}) {
  return (
    <div
      className="mx-auto w-full max-w-xl"
      data-composer-placement={placement}
    >
      <ComposerPrimitive.Root
        className={cn(
          "relative rounded-2xl border bg-card p-1.5 shadow-sm transition-colors focus-within:border-ring/40 hover:border-ring/40",
          placement === "bottom" && "flex items-end gap-2"
        )}
      >
        {placement === "bottom" ? (
          <AddSourcesButton
            isUploading={isUploading}
            onUpload={onUpload}
            className="-mr-1.5 mb-0.5"
          />
        ) : null}
        <ComposerPrimitive.Input
          autoFocus
          unstable_focusOnThreadSwitched
          disabled={!model}
          className={cn(
            "max-h-44 resize-none bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-muted-foreground",
            placement === "center"
              ? "block min-h-20 w-full pb-12"
              : "min-h-10 flex-1"
          )}
          placeholder={
            !model || providerAvailable
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
          rows={1}
          aria-label={intl.formatMessage({
            id: "chat_composer_message_aria",
            defaultMessage: "Message",
          })}
        />
        {placement === "center" ? (
          <>
            <AddSourcesButton
              isUploading={isUploading}
              onUpload={onUpload}
              className="absolute bottom-2 left-1.5"
            />
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
      {placement === "bottom" ? (
        <div className="mt-1 flex min-h-7 items-center justify-between gap-3 px-2">
          <p className="min-w-0 text-left text-[11px] text-muted-foreground select-none">
            {!model || providerAvailable
              ? intl.formatMessage({
                  id: "chat_composer_disclaimer_body",
                  defaultMessage:
                    "SurfSense can make mistakes. Check important answers.",
                })
              : intl.formatMessage({
                  id: "chat_composer_provider_offline_body",
                  defaultMessage:
                    "Historical chats remain available while the provider is offline.",
                })}
          </p>
          <ModelControl
            model={model}
            onModelSetup={onModelSetup}
            onModelSelected={onModelSelected}
          />
        </div>
      ) : null}
    </div>
  )
}
