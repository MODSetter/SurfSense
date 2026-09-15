import type { ReactNode } from "react"

import { FolderLibraryIcon, Shapes01Icon } from "@/components/ui/icons"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export type RightTab = "sources" | "artifacts"

export function RightPanel({
  inspect,
  tab,
  onTabChange,
  studio,
  sources,
  artifacts,
  artifactCount,
}: {
  inspect: ReactNode
  tab: RightTab
  onTabChange: (tab: RightTab) => void
  studio: ReactNode
  sources: ReactNode
  artifacts: ReactNode
  artifactCount: number
}) {
  if (inspect) return inspect

  return (
    <aside
      className="flex h-full min-w-0 flex-col border-l bg-background select-none"
      aria-label={
        tab === "sources" ? "Workspace sources" : "Workspace artifacts"
      }
    >
      <Tabs
        value={tab}
        onValueChange={(value) => onTabChange(value as RightTab)}
        className="h-full min-h-0 gap-0"
      >
        <header className="flex h-14 shrink-0 items-center gap-2 px-3">
          <h2 className="font-heading text-base font-medium">
            {tab === "sources" ? "Sources" : "Artifacts"}
          </h2>
          {/* The badge lives outside SegmentedControl's own overflow-hidden
              box (needed for its sliding indicator), anchored to this
              wrapper's corner instead so it doesn't get clipped. */}
          <div className="relative ml-auto h-7 w-14 shrink-0">
            <SegmentedControl
              count={2}
              selectedIndex={tab === "sources" ? 0 : 1}
              className="size-full"
            >
              <TabsList className="relative h-full bg-transparent p-0">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <TabsTrigger
                      value="sources"
                      aria-label="Sources"
                      className="h-full px-0 data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                    >
                      <FolderLibraryIcon />
                    </TabsTrigger>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" collisionPadding={8}>
                    Sources
                  </TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <TabsTrigger
                      value="artifacts"
                      aria-label={
                        artifactCount > 0
                          ? `Artifacts (${artifactCount})`
                          : "Artifacts"
                      }
                      className="h-full px-0 data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                    >
                      <Shapes01Icon />
                    </TabsTrigger>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" collisionPadding={8}>
                    Artifacts
                  </TooltipContent>
                </Tooltip>
              </TabsList>
            </SegmentedControl>
            {artifactCount > 0 ? (
              <span
                aria-hidden="true"
                className="absolute top-0 right-0 flex h-3 min-w-3 items-center justify-center rounded-full bg-primary px-0.5 text-[8px] leading-none font-semibold text-primary-foreground"
              >
                {artifactCount}
              </span>
            ) : null}
          </div>
        </header>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-5 overflow-hidden px-3 py-2">
          <div className="shrink-0">{studio}</div>
          <TabsContent value="sources" className="min-h-0 min-w-0 flex-1">
            {sources}
          </TabsContent>
          <TabsContent value="artifacts" className="min-h-0 min-w-0 flex-1">
            {artifacts}
          </TabsContent>
        </div>
      </Tabs>
    </aside>
  )
}
