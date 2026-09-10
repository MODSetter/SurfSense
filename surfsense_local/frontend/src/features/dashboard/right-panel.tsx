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
}: {
  inspect: ReactNode
  tab: RightTab
  onTabChange: (tab: RightTab) => void
  studio: ReactNode
  sources: ReactNode
  artifacts: ReactNode
}) {
  if (inspect) return inspect

  return (
    <aside
      className="flex h-full min-w-0 select-none flex-col border-l bg-background"
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
          <h2 className="font-heading text-lg font-medium">
            {tab === "sources" ? "Sources" : "Artifacts"}
          </h2>
          <SegmentedControl
            count={2}
            selectedIndex={tab === "sources" ? 0 : 1}
            className="ml-auto h-7 w-14 shrink-0"
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
                    aria-label="Artifacts"
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
        </header>
        <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          <div className="flex min-h-full w-full min-w-0 flex-col gap-5 overflow-hidden p-2">
            {studio}
            <TabsContent value="sources" className="min-w-0">
              {sources}
            </TabsContent>
            <TabsContent value="artifacts" className="min-w-0">
              {artifacts}
            </TabsContent>
          </div>
        </div>
      </Tabs>
    </aside>
  )
}
