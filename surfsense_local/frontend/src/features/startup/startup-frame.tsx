import { useState } from "react"

import {
  THREAD_BODY_CLASS,
  VIEWPORT_BOX_CLASS,
  VIEWPORT_CLASS,
  VIEWPORT_FOOTER_CLASS,
  VIEWPORT_FOOTER_INNER_CLASS,
  VIEWPORT_STYLE,
} from "@/features/chat/chat-viewport-layout"
import { ComposerOutline } from "@/features/chat/composer-outline"
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

import { readStartupLayout } from "./startup-layout"

/**
 * The dashboard's first frame without its data: the same columns, headings
 * and composer box, drawn by the dashboard's own parts, with nothing to press.
 * What needs data fades in over it once startup ends.
 */
export function StartupFrame() {
  const [layout] = useState(readStartupLayout)
  return (
    <>
      {/* The workspace rail's column, empty until its workspaces arrive. */}
      <div />
      <DashboardColumns
        sidebarWide={false}
        rightPanelOpen={layout.rightPanelOpen}
        rightPanelWide={false}
      >
        <SidebarColumn id="startup-sidebar">
          <SidebarFrame />
        </SidebarColumn>
        <ChatColumn>
          <ConversationColumn>
            <div className={THREAD_BODY_CLASS}>
              <div className={VIEWPORT_BOX_CLASS}>
                <div className={VIEWPORT_CLASS} style={VIEWPORT_STYLE}>
                  {layout.composer === "center" ? (
                    <ThreadWelcome
                      composer={<ComposerOutline placement="center" />}
                    />
                  ) : (
                    <>
                      <MessagesSkeleton />
                      <div className={VIEWPORT_FOOTER_CLASS}>
                        <div className={VIEWPORT_FOOTER_INNER_CLASS}>
                          <ComposerOutline placement="bottom" />
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
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
