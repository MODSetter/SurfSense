import { useState, type ComponentType, type ReactNode } from "react"

import { Chat01Icon, PencilEdit02Icon } from "@/components/ui/icons"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChatsDialog } from "@/features/chat/chats-dialog"
import type { ChatThread } from "@/features/chat/api"
import { intl } from "@/i18n/intl"

// A row rendered below "New chat" with the same look. Add an entry here (or
// pass one through `actions`) rather than hand-rolling another Button.
export type SidebarNavAction = {
  key: string
  label: string
  icon: ComponentType<{ className?: string }>
  onClick: () => void
  badge?: string
}

function SidebarNavButton({
  label,
  icon: Icon,
  onClick,
  badge,
}: Omit<SidebarNavAction, "key">) {
  return (
    <Button
      variant="ghost"
      className="w-full justify-start px-2"
      onClick={onClick}
    >
      <Icon />
      <span className="text-left">{label}</span>
      {badge ? (
        <Badge variant="secondary" className="ml-2 rounded-md">
          {badge}
        </Badge>
      ) : null}
    </Button>
  )
}

// The always-visible left column: brand, "New chat", the "Chats" row that
// opens every thread in a dialog, then the workspace's sources. Its own
// shell (header, footer) never moves — only what a click surfaces changes.
export function LeftSidebar({
  threads,
  activeThreadId,
  autoNamingThreadId,
  animatingTitleThreadId,
  isLoadingThreads,
  onNewChat,
  onSelectThread,
  onRenameThread,
  onDeleteThread,
  onTitleAnimationComplete,
  actions = [],
  sources,
  footer,
}: {
  threads: ChatThread[]
  activeThreadId: number | null
  autoNamingThreadId: number | null
  animatingTitleThreadId: number | null
  isLoadingThreads: boolean
  onNewChat: () => void
  onSelectThread: (id: number) => void
  onRenameThread: (id: number, title: string) => Promise<boolean>
  onDeleteThread: (id: number) => Promise<void>
  onTitleAnimationComplete: () => void
  // Extra rows below "Chats", same look. Append here to add one.
  actions?: SidebarNavAction[]
  // The workspace's sources list, already built by the caller (mirrors how
  // RightPanel takes its studio/artifacts content as nodes).
  sources: ReactNode
  // Pinned under the sources list, against the bottom edge.
  footer?: ReactNode
}) {
  const [chatsOpen, setChatsOpen] = useState(false)

  return (
    <aside className="flex h-full min-w-0 flex-col border-r bg-background select-none">
      <header className="space-y-6 px-3 py-3">
        <h2 className="truncate px-1 font-heading text-lg font-medium text-foreground select-none">
          SurfSense
        </h2>
        <div className="flex flex-col">
          <SidebarNavButton
            label={intl.formatMessage({
              id: "dashboard_sidebar_new_chat_button",
              defaultMessage: "New chat",
            })}
            icon={PencilEdit02Icon}
            onClick={onNewChat}
          />
          <SidebarNavButton
            label={intl.formatMessage({
              id: "dashboard_sidebar_chats_button",
              defaultMessage: "Chats",
            })}
            icon={Chat01Icon}
            onClick={() => setChatsOpen(true)}
          />
          {actions.map(({ key, ...action }) => (
            <SidebarNavButton key={key} {...action} />
          ))}
        </div>
      </header>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-3 pt-5 pb-2">
        {sources}
      </div>
      {footer}
      <ChatsDialog
        open={chatsOpen}
        onOpenChange={setChatsOpen}
        threads={threads}
        activeThreadId={activeThreadId}
        autoNamingThreadId={autoNamingThreadId}
        animatingTitleThreadId={animatingTitleThreadId}
        isLoading={isLoadingThreads}
        onSelect={onSelectThread}
        onNewChat={onNewChat}
        onRename={onRenameThread}
        onDelete={onDeleteThread}
        onTitleAnimationComplete={onTitleAnimationComplete}
      />
    </aside>
  )
}
