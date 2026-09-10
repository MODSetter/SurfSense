import { useEffect, useState } from "react"
import {
  CircleAlertIcon,
  LayoutGridIcon,
  PlusIcon,
  SidebarRightIcon,
  XIcon,
} from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  DETAIL_RAIL_WIDTH,
  MAIN_RAIL_WIDTH,
  SlideRail,
} from "@/components/ui/slide-rail"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { CitationPanel } from "@/features/chat/citation-panel"
import { ThreadList } from "@/features/chat/thread-list"
import { ThreadPanel } from "@/features/chat/thread-panel"
import { useChatRuntime } from "@/features/chat/use-chat-runtime"
import {
  getConnectionModels,
  getProviders,
  type ModelSelection,
} from "@/features/model-selection/api"
import {
  SettingsDialog,
  type SettingsSectionId,
} from "@/features/settings/settings-dialog"
import { SourcesPanel } from "@/features/sources/sources-panel"
import { useSources } from "@/features/sources/use-sources"
import { ArtifactPanel } from "@/features/studio/artifact-panel"
import { StudioPanel } from "@/features/studio/studio-panel"
import type { Workspace } from "@/features/workspaces/api"
import { useWorkspaces } from "@/features/workspaces/use-workspaces"
import { WorkspaceRail } from "@/features/workspaces/workspace-rail"

const SOURCES_PANEL_KEY = "sourcesPanel:v1"

type RightView =
  | { kind: "sources" }
  | { kind: "citation"; chunkId: number }
  | { kind: "artifact"; artifactId: number }

const SOURCES_VIEW: RightView = { kind: "sources" }

function readSourcesOpen() {
  try {
    return localStorage.getItem(SOURCES_PANEL_KEY) !== "collapsed"
  } catch {
    return true
  }
}

function writeSourcesOpen(open: boolean) {
  try {
    localStorage.setItem(SOURCES_PANEL_KEY, open ? "open" : "collapsed")
  } catch {
    // Private browsing and full disks throw.
  }
}

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
  const [rightView, setRightView] = useState<RightView>(SOURCES_VIEW)
  const [sourcesOpen, setSourcesOpen] = useState(readSourcesOpen)
  const sources = useSources(workspace.id)
  const chat = useChatRuntime({
    workspaceId: workspace.id,
    canSend: providerAvailable,
    selectedDocumentIds: sources.selectedDocumentIds,
    onModelRequired,
  })

  const showSources = () => setRightView(SOURCES_VIEW)
  const toggleSources = () => {
    setSourcesOpen((open) => {
      const next = !open
      writeSourcesOpen(next)
      return next
    })
  }
  const openSources = () => {
    setSourcesOpen(true)
    writeSourcesOpen(true)
  }

  return (
    <>
      <div className="titlebar-controls">
        <div className="titlebar-controls-end">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="pointer-events-auto size-6 aria-expanded:bg-transparent"
                aria-expanded={sourcesOpen}
                aria-controls="workspace-sources"
                aria-label={sourcesOpen ? "Hide right panel" : "Show right panel"}
                onClick={toggleSources}
              >
                <SidebarRightIcon />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" collisionPadding={8}>
              {sourcesOpen ? "Hide right panel" : "Show right panel"}
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
      <section className="my-2 mr-2 flex min-h-0 min-w-0 overflow-hidden rounded-[16px] border bg-background shadow-sm">
      <div className="flex h-full min-h-0 w-[272px] min-w-[232px] shrink-0 flex-col">
      <ThreadList
        threads={chat.threads}
        activeThreadId={chat.activeThreadId}
        autoNamingThreadId={chat.autoNamingThreadId}
        animatingTitleThreadId={chat.animatingTitleThreadId}
        isLoading={chat.isLoadingThreads}
        onNewChat={() => {
          showSources()
          chat.startNewChat()
        }}
        onSelect={(threadId) => {
          if (threadId !== chat.activeThreadId) showSources()
          chat.selectThread(threadId)
        }}
        onRename={chat.rename}
        onDelete={async (threadId) => {
          if (threadId === chat.activeThreadId) showSources()
          await chat.removeThread(threadId)
        }}
        onTitleAnimationComplete={chat.finishTitleAnimation}
      />
      </div>
      <div className="flex min-h-0 min-w-[520px] flex-1 flex-col">
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
        onCitation={(chunkId) => {
          openSources()
          setRightView({ kind: "citation", chunkId })
        }}
        onModelSetup={onModelRequired}
        onModelSelected={onModelSelected}
        onUpload={(files) => void sources.upload(files)}
        onTitleAnimationComplete={chat.finishTitleAnimation}
      />
      </div>
      <SlideRail
        open={sourcesOpen}
        side="end"
        width={
          rightView.kind === "sources" ? MAIN_RAIL_WIDTH : DETAIL_RAIL_WIDTH
        }
      >
        {rightView.kind === "citation" ? (
          <CitationPanel
            workspaceId={workspace.id}
            chunkId={rightView.chunkId}
            onClose={showSources}
            onOpen={(id) => void sources.openOriginal(id)}
          />
        ) : rightView.kind === "artifact" ? (
          <ArtifactPanel
            artifactId={rightView.artifactId}
            onClose={showSources}
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
              <StudioPanel
                workspaceId={workspace.id}
                documents={sources.documents}
                onOpen={(artifactId) => {
                  openSources()
                  setRightView({ kind: "artifact", artifactId })
                }}
              />
            }
          />
        )}
      </SlideRail>
    </section>
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
    const availability =
      selection.provider === "openai_compatible" &&
      selection.connection_id !== null
        ? getConnectionModels(selection.connection_id, controller.signal).then(
            (models) => models.some((model) => model.name === selection.name)
          )
        : getProviders(controller.signal).then((providers) =>
            providers.some(
              (provider) =>
                provider.name === selection.provider && provider.healthy
            )
          )
    void availability
      .then((available) => {
        setProviderAvailable(available)
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
    <main className="relative grid h-full min-w-[1168px] grid-cols-[56px_minmax(0,1fr)] overflow-hidden bg-app-shell">
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
