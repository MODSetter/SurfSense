import { ComposerPrimitive } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import {
  ArrowUp02Icon,
  ChevronDownIcon,
  CircleStopIcon,
} from "@/components/ui/icons"
import type { ModelSelection } from "@/features/model-selection/api"
import { cn } from "@/lib/utils"

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
    <div data-composer-placement={placement}>
      <ComposerPrimitive.Root className="flex items-end gap-2 rounded-2xl border bg-card p-1.5 shadow-sm focus-within:ring-2 focus-within:ring-ring/20">
        <ComposerPrimitive.Input
          className={cn(
            "max-h-44 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-muted-foreground",
            placement === "center" ? "min-h-28" : "min-h-10"
          )}
          placeholder={
            providerAvailable
              ? "Ask SurfSense about anything"
              : "Reconnect your model provider to send"
          }
          submitMode="enter"
          rows={1}
          aria-label="Message"
        />
        {!isRunning ? (
          <ComposerPrimitive.Send asChild>
            <Button
              size="icon-lg"
              className="mb-0.5 rounded-xl"
              aria-label="Send message"
            >
              <ArrowUp02Icon />
            </Button>
          </ComposerPrimitive.Send>
        ) : (
          <ComposerPrimitive.Cancel asChild>
            <Button
              size="icon-lg"
              variant="secondary"
              className="mb-0.5 rounded-xl"
              aria-label="Stop generating"
            >
              <CircleStopIcon />
            </Button>
          </ComposerPrimitive.Cancel>
        )}
      </ComposerPrimitive.Root>
      <div className="mt-1 flex min-h-7 items-center justify-between gap-3 px-2">
        <p className="min-w-0 text-left text-[11px] text-muted-foreground">
          {providerAvailable
            ? `${model.name} runs locally. Check important answers.`
            : "Historical chats remain available while the provider is offline."}
        </p>
        <button
          type="button"
          onClick={onModelSetup}
          className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-1.5 py-1 text-[11px] font-normal text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:outline-none"
          title="Change model"
          aria-label={`Model ${model.name} on ${model.provider}. Change model.`}
        >
          <span>{model.name}</span>
          <span>{providerAvailable ? model.provider : "Provider offline"}</span>
          <ChevronDownIcon className="size-3" />
        </button>
      </div>
    </div>
  )
}
