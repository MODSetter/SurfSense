import type { ReactNode } from "react"

import { SegmentedControl } from "@/components/ui/segmented-control"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export type RightTab = "sources" | "artifacts"

export function RightPanel({
  inspect,
  tab,
  onTabChange,
  sourcesAction,
  studio,
  sources,
  artifacts,
}: {
  inspect: ReactNode
  tab: RightTab
  onTabChange: (tab: RightTab) => void
  sourcesAction: ReactNode
  studio: ReactNode
  sources: ReactNode
  artifacts: ReactNode
}) {
  if (inspect) return inspect

  return (
    <aside
      className="flex h-full min-w-0 flex-col border-l bg-background"
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
          <SegmentedControl
            count={2}
            selectedIndex={tab === "sources" ? 0 : 1}
            className="mr-auto h-7 w-40 shrink-0"
          >
            <TabsList className="relative h-full bg-transparent p-0">
              <TabsTrigger
                value="sources"
                className="h-full data-[state=active]:bg-transparent data-[state=active]:shadow-none"
              >
                Sources
              </TabsTrigger>
              <TabsTrigger
                value="artifacts"
                className="h-full data-[state=active]:bg-transparent data-[state=active]:shadow-none"
              >
                Artifacts
              </TabsTrigger>
            </TabsList>
          </SegmentedControl>
          {tab === "sources" ? sourcesAction : null}
        </header>
        <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          <div className="flex min-h-full w-full min-w-0 flex-col gap-3 overflow-hidden p-2">
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
