import { useCallback, useEffect, useState } from "react"
import { CircleAlertIcon, LayoutGridIcon, PlusIcon, XIcon } from "lucide-react"

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
import type { Citation } from "@/features/chat/sse"
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
  const [citations, setCitations] = useState<Citation[]>([])
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(
    null
  )
  const sources = useSources(workspace.id)
  const handleCitations = useCallback((next: Citation[]) => {
    setCitations(next)
    setSelectedCitation(null)
  }, [])
  const chat = useChatRuntime({
    workspaceId: workspace.id,
    canSend: providerAvailable,
    onCitations: handleCitations,
    onModelRequired,
  })

  const openSource = (documentId: number, citation?: Citation) => {
    setSelectedCitation(citation ?? null)
    void sources.openDocument(documentId)
  }

  return (
    <>
      <ThreadList
        workspaceName={workspace.name}
        threads={chat.threads}
        activeThreadId={chat.activeThreadId}
        isLoading={chat.isLoadingThreads}
        onNewChat={chat.startNewChat}
        onSelect={chat.selectThread}
        onDelete={chat.removeThread}
      />
      <ThreadPanel
        runtime={chat.runtime}
        thread={chat.activeThread}
        model={selection}
        documents={sources.documents}
        error={chat.error}
        isLoading={chat.isLoadingMessages}
        isRunning={chat.isRunning}
        providerAvailable={providerAvailable}
        onCitation={(citation) => openSource(citation.document_id, citation)}
        onModelSetup={onModelRequired}
      />
      <SourcesPanel
        documents={sources.documents}
        citations={citations}
        selectedDocument={sources.selectedDocument}
        selectedCitation={selectedCitation}
        isLoading={sources.isLoading}
        isLoadingPreview={sources.isLoadingPreview}
        isUploading={sources.isUploading}
        uploadOutcome={sources.uploadOutcome}
        error={sources.error}
        onOpen={openSource}
        onBack={() => {
          setSelectedCitation(null)
          sources.closePreview()
        }}
        onRetry={(id) => void sources.retry(id)}
        onUpload={(files) => void sources.upload(files)}
        onDismissUploadOutcome={sources.dismissUploadOutcome}
      />
    </>
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
    <main className="flex h-svh items-center justify-center bg-background p-8">
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
    <main className="relative grid h-svh min-w-[1120px] grid-cols-[56px_minmax(232px,272px)_minmax(520px,1fr)_minmax(280px,320px)] overflow-hidden">
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
