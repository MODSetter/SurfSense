import { useState } from "react"

import {
  ConversationBody,
  ConversationScroll,
} from "@/features/chat/conversation-scroll"
import { ConversationColumn } from "@/features/chat/conversation-column"
import { MessagesSkeleton } from "@/features/chat/messages-skeleton"
import { ThreadWelcome } from "@/features/chat/thread-welcome"
import {
  ChatColumn,
  DashboardColumns,
  RightPanelRail,
  SidebarColumn,
} from "@/features/dashboard/dashboard-columns"
import { RightPanel } from "@/features/dashboard/right-panel"
import { SidebarFrame } from "@/features/dashboard/sidebar-frame"

import { StartupComposer } from "./startup-composer"
import { readStartupLayout } from "./startup-layout"

/**
 * The dashboard's first frame without its data: the same columns and
 * headings, drawn by the dashboard's own parts. A new chat's box takes typing;
 * an open thread shows its messages' skeleton and gets its composer with them.
 * What needs data fades in once startup ends.
 */
export function StartupFrame() {
  const [layout] = useState(readStartupLayout)
  return (
    <>
      {/* The workspace rail's column, empty until its workspaces arrive. */}
      <div />
      <DashboardColumns
        sidebarOpen={layout.sidebarOpen}
        sidebarWide={false}
        rightPanelOpen={layout.rightPanelOpen}
        rightPanelWide={false}
      >
        <SidebarColumn id="startup-sidebar">
          <SidebarFrame />
        </SidebarColumn>
        <ChatColumn>
          <ConversationColumn>
            <ConversationBody>
              <ConversationScroll>
                {layout.composer === "center" ? (
                  <ThreadWelcome
                    composer={<StartupComposer mentions={layout.mentions} />}
                  />
                ) : (
                  // The composer arrives with the thread it follows.
                  <MessagesSkeleton />
                )}
              </ConversationScroll>
            </ConversationBody>
          </ConversationColumn>
        </ChatColumn>
        <RightPanelRail open={layout.rightPanelOpen}>
          <div className="h-full min-h-0">
            <RightPanel inspect={null} studio={null} artifacts={null} />
          </div>
        </RightPanelRail>
      </DashboardColumns>
    </>
  )
}
