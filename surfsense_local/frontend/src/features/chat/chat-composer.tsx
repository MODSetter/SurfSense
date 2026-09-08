import { ComposerPrimitive } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import {
  ArrowUp02Icon,
  ChevronDownIcon,
  CircleStopIcon,
} from "@/components/ui/icons"
import type { ModelSelection } from "@/features/model-selection/api"
import { cn } from "@/lib/utils"

function ModelButton({
  model,
  onModelSetup,
  className,
}: {
  model: ModelSelection
  onModelSetup: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onModelSetup}
      className={cn(
        "flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-1.5 py-1 text-[11px] font-normal text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:outline-none",
        className
      )}
      title="Change model"
      aria-label={`Model ${model.name}. Change model.`}
    >
      <span>{model.name}</span>
      <ChevronDownIcon className="size-3" />
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
          aria-label="Send message"
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
        aria-label="Stop generating"
      >
        <CircleStopIcon />
      </Button>
    </ComposerPrimitive.Cancel>
  )
}

export function ChatComposer({
  placement,
  model,
  isRunning,
  providerAvailable,
  onModelSetup,
}: {
  placement: "center" | "bottom"
  model: ModelSelection
  isRunning: boolean
  providerAvailable: boolean
  onModelSetup: () => void
}) {
  return (
    <div
      className="mx-auto w-full max-w-xl"
      data-composer-placement={placement}
    >
      <ComposerPrimitive.Root
        className={cn(
          "relative rounded-2xl border bg-card p-1.5 shadow-sm focus-within:ring-2 focus-within:ring-ring/20",
          placement === "bottom" && "flex items-end gap-2"
        )}
      >
        <ComposerPrimitive.Input
          className={cn(
            "max-h-44 resize-none bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-muted-foreground",
            placement === "center"
              ? "block min-h-20 w-full pb-12"
              : "min-h-10 flex-1"
          )}
          placeholder={
            providerAvailable
              ? placement === "center"
                ? "Turn your sources into answers"
                : "Follow up on this answer"
              : "Reconnect your model provider to send"
          }
          submitMode="enter"
          rows={1}
          aria-label="Message"
        />
        {placement === "center" ? (
          <div className="absolute right-1.5 bottom-2 flex items-center gap-2">
            <ModelButton
              model={model}
              onModelSetup={onModelSetup}
              className="h-9 rounded-xl px-3 text-sm"
            />
            <ComposerAction isRunning={isRunning} />
          </div>
        ) : (
          <ComposerAction isRunning={isRunning} className="mb-0.5" />
        )}
      </ComposerPrimitive.Root>
      {placement === "bottom" ? (
        <div className="mt-1 flex min-h-7 items-center justify-between gap-3 px-2">
          <p className="min-w-0 text-left text-[11px] text-muted-foreground">
            {providerAvailable
              ? `${model.name} runs locally. Check important answers.`
              : "Historical chats remain available while the provider is offline."}
          </p>
          <ModelButton model={model} onModelSetup={onModelSetup} />
        </div>
      ) : null}
    </div>
  )
}
