import type { ReactNode, Ref } from "react"

import { Button } from "@/components/ui/button"
import { XIcon } from "@/components/ui/icons"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

export function DetailPanel({
  title,
  ariaLabel,
  actions,
  onClose,
  closeLabel,
  bodyRef,
  flush = false,
  children,
}: {
  title: string
  ariaLabel: string
  actions?: ReactNode
  onClose: () => void
  closeLabel: string
  bodyRef?: Ref<HTMLDivElement>
  flush?: boolean
  children: ReactNode
}) {
  return (
    <aside
      className="flex h-full min-w-0 flex-col border-l bg-background"
      aria-label={ariaLabel}
    >
      <div className="grid h-14 shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-3">
        <p className="min-w-0 truncate text-sm text-muted-foreground">{title}</p>
        <div className="flex items-center gap-1">
          {actions}
          <Separator
            orientation="vertical"
            className="mx-1.5 data-vertical:h-4 data-vertical:w-px data-vertical:self-center"
          />
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label={closeLabel}
          >
            <XIcon />
          </Button>
        </div>
      </div>
      <div
        ref={bodyRef}
        className={cn(
          "min-h-0 flex-1",
          flush ? "overflow-hidden" : "overflow-y-auto px-5 py-4"
        )}
      >
        {children}
      </div>
    </aside>
  )
}
