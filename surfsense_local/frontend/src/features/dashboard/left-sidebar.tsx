import { memo, useState, type ComponentType, type ReactNode } from "react"

import {
  Chat01Icon,
  CircleAlertIcon,
  Loader2Icon,
  PencilEdit02Icon,
} from "@/components/ui/icons"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChatsDialog } from "@/features/chat/chats-dialog"
import type { ChatThread } from "@/features/chat/api"
import type { RunState } from "@/features/chat/runs/run-store"
import { intl } from "@/i18n/intl"

// A row rendered below "New chat" with the same look. Add an entry here (or
// pass one through `actions`) rather than hand-rolling another Button.
export type SidebarNavAction = {
  key: string
  label: string
  icon: ComponentType<{ className?: string }>
  onClick: () => void
  badge?: string
  // Something happening behind the row, at its end; `ariaLabel` says it.
  indicator?: ReactNode
  ariaLabel?: string
}

function SidebarNavButton({
  label,
  icon: Icon,
  onClick,
  badge,
  indicator,
  ariaLabel,
}: Omit<SidebarNavAction, "key">) {
  return (
    <Button
      variant="ghost"
      className="w-full justify-start px-2"
      onClick={onClick}
      aria-label={ariaLabel}
    >
      <Icon />
      <span className="text-left">{label}</span>
      {badge ? (
        <Badge variant="secondary" className="ml-2 rounded-md">
          {badge}
        </Badge>
      ) : null}
      {indicator ? (
        <span
          aria-hidden
          className="ml-auto flex items-center text-muted-foreground"
        >
          {indicator}
        </span>
      ) : null}
    </Button>
  )
}

/**
 * What the Chats row says about threads other than the open one: an alert when
 * the agent waits on the user's approval, else a dot when a reply is unread,
 * else a spinner while any is writing or waiting. One mark, the one to act on
 * first; the counts are for screen readers.
 */
function chatsActivity(
  activeThreadId: number | null,
  runStates: Record<number, RunState>,
  unreadThreadIds: number[]
): { indicator: ReactNode; ariaLabel: string } | null {
  const elsewhere = (id: number) => id !== activeThreadId
  const asking = Object.entries(runStates).filter(
    ([id, run]) => elsewhere(Number(id)) && run.state === "needs-approval"
  ).length
  if (asking > 0) {
    return {
      indicator: <CircleAlertIcon className="size-3 text-primary" />,
      ariaLabel: intl.formatMessage(
        {
          id: "dashboard_sidebar_chats_needs_approval_aria",
          defaultMessage:
            "Chats, {count, plural, one {# reply} other {# replies}} waiting for your approval",
        },
        { count: asking }
      ),
    }
  }
  const unread = unreadThreadIds.filter(elsewhere).length
  if (unread > 0) {
    return {
      indicator: <span className="size-1.5 rounded-full bg-primary" />,
      ariaLabel: intl.formatMessage(
        {
          id: "dashboard_sidebar_chats_unread_aria",
          defaultMessage:
            "Chats, {count, plural, one {# new reply} other {# new replies}}",
        },
        { count: unread }
      ),
    }
  }
  const running = Object.keys(runStates).map(Number).filter(elsewhere).length
  if (running > 0) {
    return {
      indicator: (
        <Loader2Icon className="size-3 animate-spin motion-reduce:animate-none" />
      ),
      ariaLabel: intl.formatMessage(
        {
          id: "dashboard_sidebar_chats_running_aria",
          defaultMessage:
            "Chats, {count, plural, one {# reply} other {# replies}} being written",
        },
        { count: running }
      ),
    }
  }
  return null
}

const NO_RUNS: Record<number, RunState> = {}
const NO_UNREAD: number[] = []
const NO_ACTIONS: SidebarNavAction[] = []

// The always-visible left column: brand, "New chat", the "Chats" row that
// opens every thread in a dialog, then the workspace's sources. Its own
// shell (header, footer) never moves — only what a click surfaces changes.
// Memoized: the dashboard re-renders for each streamed token and column drag.
export const LeftSidebar = memo(function LeftSidebar({
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
  runStates = NO_RUNS,
  unreadThreadIds = NO_UNREAD,
  actions = NO_ACTIONS,
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
  // Threads with a reply being written or waiting, and those finished unread.
  runStates?: Record<number, RunState>
  unreadThreadIds?: number[]
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
        <h2 className="truncate px-1 brand-wordmark text-xl text-foreground select-none">
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
            {...chatsActivity(activeThreadId, runStates, unreadThreadIds)}
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
        runStates={runStates}
        unreadThreadIds={unreadThreadIds}
      />
    </aside>
  )
})
