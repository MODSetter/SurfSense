import { useEffect, useState } from "react"
import {
  CircleAlertIcon,
  LayoutGridIcon,
  PlusIcon,
  XIcon,
} from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { CitationPanel } from "@/features/chat/citation-panel"
import { ThreadList } from "@/features/chat/thread-list"
import { ThreadPanel } from "@/features/chat/thread-panel"
import { useChatRuntime } from "@/features/chat/use-chat-runtime"
import {
  getProviders,
  type ModelSelection,
} from "@/features/model-selection/api"
import {
  SettingsDialog,
  type SettingsSectionId,
} from "@/features/settings/settings-dialog"
import { SourcesPanel } from "@/features/sources/sources-panel"
import { useSources } from "@/features/sources/use-sources"
import { StudioDialog } from "@/features/studio/studio-dialog"
import type { Workspace } from "@/features/workspaces/api"
import { useWorkspaces } from "@/features/workspaces/use-workspaces"
import { WorkspaceRail } from "@/features/workspaces/workspace-rail"

function WorkspaceDashboard({
  workspace,
  selection,
  providerAvailable,
  onModelRequired,
  onModelSelected,
}: {
  workspace: Workspace
  selection: ModelSelection | null
  providerAvailable: boolean
  onModelRequired: () => void
  onModelSelected: (selection: ModelSelection) => void
}) {
  const [citationChunkId, setCitationChunkId] = useState<number | null>(null)
  const sources = useSources(workspace.id)
  const chat = useChatRuntime({
    workspaceId: workspace.id,
    canSend: providerAvailable,
    selectedDocumentIds: sources.selectedDocumentIds,
    onModelRequired,
  })

  const closeCitation = () => setCitationChunkId(null)

  return (
    <section className="my-2 mr-2 grid min-h-0 grid-cols-[minmax(232px,272px)_minmax(520px,1fr)_minmax(280px,320px)] grid-rows-[minmax(0,1fr)] overflow-hidden rounded-[16px] border bg-background shadow-sm">
      <ThreadList
        threads={chat.threads}
        activeThreadId={chat.activeThreadId}
        autoNamingThreadId={chat.autoNamingThreadId}
        animatingTitleThreadId={chat.animatingTitleThreadId}
        isLoading={chat.isLoadingThreads}
        onNewChat={() => {
          closeCitation()
          chat.startNewChat()
        }}
        onSelect={(threadId) => {
          if (threadId !== chat.activeThreadId) closeCitation()
          chat.selectThread(threadId)
        }}
        onRename={chat.rename}
        onDelete={async (threadId) => {
          if (threadId === chat.activeThreadId) closeCitation()
          await chat.removeThread(threadId)
        }}
        onTitleAnimationComplete={chat.finishTitleAnimation}
      />
      <ThreadPanel
        runtime={chat.runtime}
        thread={chat.activeThread}
        view={chat.conversationView}
        model={selection}
        error={chat.error}
        isLoading={chat.isLoadingMessages}
        isRunning={chat.isRunning}
        isUploading={sources.isUploading}
        animateTitle={chat.activeThreadId === chat.animatingTitleThreadId}
        providerAvailable={providerAvailable}
        onCitation={setCitationChunkId}
        onModelSetup={onModelRequired}
        onModelSelected={onModelSelected}
        onUpload={(files) => void sources.upload(files)}
        onTitleAnimationComplete={chat.finishTitleAnimation}
      />
      {citationChunkId !== null ? (
        <CitationPanel
          workspaceId={workspace.id}
          chunkId={citationChunkId}
          onClose={closeCitation}
          onOpen={(id) => void sources.openOriginal(id)}
        />
      ) : (
        <SourcesPanel
          documents={sources.documents}
          selectedDocumentIds={sources.selectedDocumentIds}
          highlightedDocumentId={null}
          isLoading={sources.isLoading}
          isUploading={sources.isUploading}
          isDeleting={sources.isDeleting}
          error={sources.error}
          onOpen={(id) => void sources.openOriginal(id)}
          onReveal={(id) => void sources.revealOriginal(id)}
          onRetry={(id) => void sources.retry(id)}
          onDelete={(id) => void sources.deleteOne(id)}
          onDeleteSelected={() => void sources.deleteSelected()}
          onSelectionChange={sources.setDocumentSelected}
          onUpload={(files) => void sources.upload(files)}
          studioSlot={
            <StudioDialog
              workspaceId={workspace.id}
              documents={sources.documents}
            />
          }
        />
      )}
    </section>
  )
}

function WorkspacesEmpty({
  isMutating,
  onCreate,
}: {
  isMutating: boolean
  onCreate: (name: string) => Promise<boolean>
}) {
  return (
    <main className="flex h-full items-center justify-center bg-background p-8">
      <div className="flex max-w-sm flex-col items-center text-center">
        <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-muted">
          <LayoutGridIcon className="size-5" />
        </div>
        <h1 className="font-heading text-xl font-medium">No workspaces</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          A workspace keeps a source library and its chats together.
        </p>
        <Button
          className="mt-5"
          disabled={isMutating}
          onClick={() => void onCreate("My Workspace")}
        >
          <PlusIcon />
          Create workspace
        </Button>
      </div>
    </main>
  )
}

export function DashboardPage({
  selection,
  initialWorkspaces,
  onModelUnavailable = () => undefined,
  onModelSelected,
}: {
  selection: ModelSelection | null
  initialWorkspaces: Workspace[]
  onModelUnavailable?: () => void
  onModelSelected: (selection: ModelSelection) => void
}) {
  const workspaces = useWorkspaces(initialWorkspaces)
  const [providerAvailable, setProviderAvailable] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsSection, setSettingsSection] =
    useState<SettingsSectionId>("general")

  const openSettings = (section: SettingsSectionId) => {
    setSettingsSection(section)
    setSettingsOpen(true)
  }

  useEffect(() => {
    if (!selection) {
      return
    }
    const controller = new AbortController()
    void getProviders(controller.signal)
      .then((providers) => {
        setProviderAvailable(
          providers.some(
            (provider) =>
              provider.name === selection.provider && provider.healthy
          )
        )
      })
      .catch(() => setProviderAvailable(false))
    return () => controller.abort()
  }, [selection])

  if (!workspaces.activeWorkspace) {
    return (
      <WorkspacesEmpty
        isMutating={workspaces.isMutating}
        onCreate={workspaces.create}
      />
    )
  }

  return (
    <main className="relative grid h-full min-w-[1120px] grid-cols-[56px_minmax(0,1fr)] overflow-hidden bg-app-shell">
      <WorkspaceRail
        workspaces={workspaces.workspaces}
        activeWorkspaceId={workspaces.activeWorkspace.id}
        isMutating={workspaces.isMutating}
        onSelect={workspaces.select}
        onCreate={workspaces.create}
        onRename={workspaces.rename}
        onDelete={workspaces.remove}
        onOpenSettings={() => openSettings("general")}
      />
      <WorkspaceDashboard
        key={workspaces.activeWorkspace.id}
        workspace={workspaces.activeWorkspace}
        selection={selection}
        providerAvailable={selection !== null && providerAvailable}
        onModelRequired={() => openSettings("models")}
        onModelSelected={onModelSelected}
      />
      <SettingsDialog
        open={settingsOpen}
        section={settingsSection}
        onOpenChange={setSettingsOpen}
        onSectionChange={setSettingsSection}
        onModelUnavailable={onModelUnavailable}
        onModelSelected={onModelSelected}
      />
      {workspaces.error ? (
        <Alert
          variant="destructive"
          className="absolute top-4 left-1/2 z-40 w-auto max-w-lg -translate-x-1/2 shadow-lg"
        >
          <CircleAlertIcon />
          <AlertTitle>Workspace action failed</AlertTitle>
          <AlertDescription>{workspaces.error}</AlertDescription>
          <Button
            variant="ghost"
            size="icon-sm"
            className="absolute top-1 right-1"
            aria-label="Dismiss workspace error"
            onClick={workspaces.clearError}
          >
            <XIcon />
          </Button>
        </Alert>
      ) : null}
    </main>
  )
}
