import { useEffect, useRef, useState } from "react"
import {
  CircleAlertIcon,
  LayoutGridIcon,
  PlusIcon,
  XIcon,
} from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ThreadList } from "@/features/chat/thread-list"
import { ThreadPanel } from "@/features/chat/thread-panel"
import { useChatRuntime } from "@/features/chat/use-chat-runtime"
import {
  getProviders,
  type ModelSelection,
} from "@/features/model-selection/api"
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
}: {
  workspace: Workspace
  selection: ModelSelection
  providerAvailable: boolean
  onModelRequired: () => void
}) {
  const [highlightedDocumentId, setHighlightedDocumentId] = useState<
    number | null
  >(null)
  const highlightTimeout = useRef<number | null>(null)
  const sources = useSources(workspace.id)
  const chat = useChatRuntime({
    workspaceId: workspace.id,
    canSend: providerAvailable,
    selectedDocumentIds: sources.selectedDocumentIds,
    onModelRequired,
  })

  const clearDocumentHighlight = () => {
    if (highlightTimeout.current !== null) {
      window.clearTimeout(highlightTimeout.current)
      highlightTimeout.current = null
    }
    setHighlightedDocumentId(null)
  }

  const highlightDocument = (documentId: number) => {
    if (highlightTimeout.current !== null) {
      window.clearTimeout(highlightTimeout.current)
    }
    setHighlightedDocumentId(documentId)
    highlightTimeout.current = window.setTimeout(() => {
      setHighlightedDocumentId(null)
      highlightTimeout.current = null
    }, 3000)
  }

  useEffect(
    () => () => {
      if (highlightTimeout.current !== null) {
        window.clearTimeout(highlightTimeout.current)
      }
    },
    []
  )

  return (
    <section className="my-2 mr-2 grid min-h-0 grid-cols-[minmax(232px,272px)_minmax(520px,1fr)_minmax(280px,320px)] grid-rows-[minmax(0,1fr)] overflow-hidden rounded-[16px] border bg-background shadow-sm">
      <ThreadList
        threads={chat.threads}
        activeThreadId={chat.activeThreadId}
        autoNamingThreadId={chat.autoNamingThreadId}
        animatingTitleThreadId={chat.animatingTitleThreadId}
        isLoading={chat.isLoadingThreads}
        onNewChat={() => {
          clearDocumentHighlight()
          chat.startNewChat()
        }}
        onSelect={(threadId) => {
          if (threadId !== chat.activeThreadId) clearDocumentHighlight()
          chat.selectThread(threadId)
        }}
        onRename={chat.rename}
        onDelete={async (threadId) => {
          if (threadId === chat.activeThreadId) clearDocumentHighlight()
          await chat.removeThread(threadId)
        }}
        onTitleAnimationComplete={chat.finishTitleAnimation}
      />
      <ThreadPanel
        runtime={chat.runtime}
        thread={chat.activeThread}
        view={chat.conversationView}
        model={selection}
        documents={sources.documents}
        error={chat.error}
        isLoading={chat.isLoadingMessages}
        isRunning={chat.isRunning}
        animateTitle={chat.activeThreadId === chat.animatingTitleThreadId}
        providerAvailable={providerAvailable}
        onCitation={(citation) => highlightDocument(citation.document_id)}
        onModelSetup={onModelRequired}
        onTitleAnimationComplete={chat.finishTitleAnimation}
      />
      <SourcesPanel
        documents={sources.documents}
        selectedDocumentIds={sources.selectedDocumentIds}
        highlightedDocumentId={highlightedDocumentId}
        isLoading={sources.isLoading}
        isUploading={sources.isUploading}
        isDeleting={sources.isDeleting}
        error={sources.error}
        onOpen={(id) => void sources.openOriginal(id)}
        onReveal={(id) => void sources.revealOriginal(id)}
        onRetry={(id) => void sources.retry(id)}
        onDelete={(id) => {
          if (id === highlightedDocumentId) clearDocumentHighlight()
          void sources.deleteOne(id)
        }}
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
  onModelRequired,
}: {
  selection: ModelSelection
  initialWorkspaces: Workspace[]
  onModelRequired: () => void
}) {
  const workspaces = useWorkspaces(initialWorkspaces)
  const [providerAvailable, setProviderAvailable] = useState(true)

  useEffect(() => {
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
  }, [selection.provider])

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
      />
      <WorkspaceDashboard
        key={workspaces.activeWorkspace.id}
        workspace={workspaces.activeWorkspace}
        selection={selection}
        providerAvailable={providerAvailable}
        onModelRequired={onModelRequired}
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
