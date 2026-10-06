import { useCallback, useEffect, useRef, useState } from "react"
import { ApprovalDialog } from "@/features/agent/approval-dialog"
import { toast } from "sonner"
import {
  CircleAlertIcon,
  LayoutGridIcon,
  PlusIcon,
  SidebarRightIcon,
  UnplugIcon,
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
import { consentPlaceholder } from "@/features/chat/model-issue"
import { askEgress } from "@/features/egress/ask-egress"
import { setDestinationEnabled } from "@/features/egress/api"
import { ModelIssueNotice } from "@/features/chat/model-issue-notice"
import { canSkipThinking } from "@/features/chat/thinking-preference"
import { ThreadPanel } from "@/features/chat/thread-panel"
import { useChatRuntime } from "@/features/chat/use-chat-runtime"
import { useHelpMenuReport } from "@/features/feedback/help-menu-report"
import type { ImportAccepted } from "@/features/migration/api"
import { ImportBundleButton } from "@/features/migration/import-bundle"
import { modelKey, type ModelSelection } from "@/features/models/selection/api"
import {
  checkAvailability,
  type Availability,
  type ModelIssue,
} from "@/features/models/selection/availability"
import {
  SettingsDialog,
  type SettingsSectionId,
} from "@/features/settings/settings-dialog"
import { SourcesPanel } from "@/features/sources/sources-panel"
import { useSources } from "@/features/sources/use-sources"
import { getFileViewer } from "@/features/file-viewers/registry"
import { SourcePreviewPanel } from "@/features/source-preview/source-preview-panel"
import { ArtifactList } from "@/features/studio/artifact-list"
import { ArtifactPanel } from "@/features/studio/artifact-panel"
import { OpenArtifactContext } from "@/features/studio/open-artifact"
import { StudioPanel } from "@/features/studio/studio-panel"
import { useStudio } from "@/features/studio/use-studio"
import { UpdateButton } from "@/features/updates/update-settings"
import type { Workspace } from "@/features/workspaces/api"
import { useWorkspaces } from "@/features/workspaces/use-workspaces"
import { intl } from "@/i18n/intl"
import { WorkspaceRail } from "@/features/workspaces/workspace-rail"
import {
  readRightPanelOpen,
  readSourcePreview,
  writeRightPanelOpen,
  writeSourcePreview,
} from "./chrome-prefs"
import { LeftSidebar } from "./left-sidebar"
import { RightPanel } from "./right-panel"
import { SidebarFooter } from "./sidebar-footer"

// Clicking "N sources" in the composer used to switch the right rail to its
// Sources tab. Sources now live in the always-visible left sidebar, so the
// same click just brings that list into view instead.
const LEFT_SOURCES_ID = "workspace-left-sources"

type Inspect =
  | { kind: "citation"; chunkId: number }
  | { kind: "artifact"; artifactId: number }
  | null

// The left sidebar's resting width, w-68.
const SIDEBAR_WIDTH = 272

function WorkspaceDashboard({
  workspace,
  selection,
  providerAvailable,
  modelIssue,
  needsConsent,
  onModelIssueSettings,
  onAllowModelIssue,
  onModelRequired,
  onModelSelected,
  onOpenLicense,
  onOpenAudioSettings,
  modelsVisited,
}: {
  workspace: Workspace
  selection: ModelSelection | null
  providerAvailable: boolean
  modelIssue: ModelIssue | null
  needsConsent: boolean
  onModelIssueSettings: () => void
  onAllowModelIssue: () => void
  onModelRequired: () => void
  onModelSelected: (selection: ModelSelection) => void
  onOpenLicense: () => void
  onOpenAudioSettings: () => void
  modelsVisited: number
}) {
  const [inspect, setInspect] = useState<Inspect>(null)
  const [rightPanelOpen, setRightPanelOpen] = useState(readRightPanelOpen)
  const [sourcePreviewId, setSourcePreviewId] = useState<number | null>(() =>
    readSourcePreview(workspace.id)
  )
  const sources = useSources(workspace.id)
  // Which formats Studio offers is the server's answer to what is selected,
  // so it has to be asked again when that changes. The chat model is named
  // here directly; the image model is chosen inside the settings dialog and
  // reported only by `modelsVisited`, which counts closing it.
  const studio = useStudio(
    workspace.id,
    `${selection ? modelKey(selection) : "none"}:${modelsVisited}`
  )
  const selectedSourceTitles = sources.includedDocumentIds.map(
    (id) =>
      sources.documents.find((document) => document.id === id)?.title ?? ""
  )
  const chat = useChatRuntime({
    workspaceId: workspace.id,
    canSend: providerAvailable,
    selectedDocumentIds: sources.includedDocumentIds,
    selectedSourceTitles,
    sourceScope: sources.sourceScope,
    readsImages: selection?.reads_images === true,
    canSkipThinking: canSkipThinking(selection),
    onModelRequired,
  })
  const sourcePreview = sources.documents.find(
    (document) => document.id === sourcePreviewId
  )
  const sourcePreviewOpen =
    sourcePreview?.document_type === "FILE" &&
    getFileViewer(sourcePreview.mime_type) !== null

  useEffect(() => {
    if (sourcePreviewId === null || sources.isLoading) return
    if (
      !sourcePreview ||
      sourcePreview.document_type !== "FILE" ||
      !getFileViewer(sourcePreview.mime_type)
    ) {
      writeSourcePreview(workspace.id, null)
    }
  }, [sourcePreview, sourcePreviewId, sources.isLoading, workspace.id])

  const composerHold =
    modelIssue && needsConsent ? consentPlaceholder(modelIssue) : undefined

  const closeInspect = () => setInspect(null)
  const startNewChat = () => {
    closeInspect()
    chat.startNewChat()
  }
  const closeSourcePreview = () => {
    setSourcePreviewId(null)
    writeSourcePreview(workspace.id, null)
  }
  const toggleSourcePreview = (documentId: number) => {
    const next = sourcePreviewId === documentId ? null : documentId
    setSourcePreviewId(next)
    writeSourcePreview(workspace.id, next)
  }
  const toggleRightPanel = () => {
    setRightPanelOpen((open) => {
      const next = !open
      writeRightPanelOpen(next)
      return next
    })
  }
  const openRightPanel = useCallback(() => {
    setRightPanelOpen(true)
    writeRightPanelOpen(true)
  }, [])
  // Stable: it is a context value, and this page re-renders on every streamed
  // token, which would re-render every agent step in the thread.
  const openArtifact = useCallback(
    (artifactId: number) => {
      openRightPanel()
      setInspect({ kind: "artifact", artifactId })
    },
    [openRightPanel]
  )
  return (
    <OpenArtifactContext.Provider value={openArtifact}>
      <div className="titlebar-controls">
        <div className="titlebar-controls-end">
          <UpdateButton />
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="pointer-events-auto size-6 aria-expanded:bg-transparent"
                  aria-expanded={rightPanelOpen}
                  aria-controls="workspace-right-panel"
                  aria-label={
                    rightPanelOpen
                      ? intl.formatMessage({
                          id: "dashboard_right_panel_hide_aria",
                          defaultMessage: "Hide right panel",
                        })
                      : intl.formatMessage({
                          id: "dashboard_right_panel_show_aria",
                          defaultMessage: "Show right panel",
                        })
                  }
                  onClick={toggleRightPanel}
                >
                  <SidebarRightIcon />
                </Button>
              }
            />
            <TooltipContent side="bottom" collisionPadding={8}>
              {rightPanelOpen
                ? intl.formatMessage({
                    id: "dashboard_right_panel_hide_tooltip",
                    defaultMessage: "Hide right panel",
                  })
                : intl.formatMessage({
                    id: "dashboard_right_panel_show_tooltip",
                    defaultMessage: "Show right panel",
                  })}
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
      <section className="my-2 mr-2 flex min-h-0 min-w-0 overflow-hidden rounded-[16px] border bg-background shadow-sm">
        {/* A preview takes over the left column and widens it, as an
            inspected artifact does the right one; the right panel stays put.
            It shrinks, down to the sidebar's width, before the chat or the
            right panel lose room on a narrow window. */}
        <div
          className="flex h-full min-h-0 min-w-68 flex-col transition-[width] duration-[240ms] ease-[cubic-bezier(0.4,0,0.2,1)] motion-reduce:transition-none"
          style={{
            width: sourcePreviewOpen ? DETAIL_RAIL_WIDTH : SIDEBAR_WIDTH,
          }}
        >
          {sourcePreviewOpen && sourcePreview ? (
            <SourcePreviewPanel
              workspaceId={workspace.id}
              document={sourcePreview}
              onOpen={() => void sources.openOriginal(sourcePreview.id)}
              onClose={closeSourcePreview}
            />
          ) : null}
          {/* Hidden, not unmounted, so the sources list keeps its scroll. */}
          <div
            hidden={sourcePreviewOpen}
            className="flex h-full min-h-0 flex-col"
          >
            <LeftSidebar
              threads={chat.threads}
              activeThreadId={chat.activeThreadId}
              autoNamingThreadId={chat.autoNamingThreadId}
              animatingTitleThreadId={chat.animatingTitleThreadId}
              isLoadingThreads={chat.isLoadingThreads}
              onNewChat={startNewChat}
              onSelectThread={(threadId) => {
                if (threadId !== chat.activeThreadId) closeInspect()
                chat.selectThread(threadId)
              }}
              onRenameThread={chat.rename}
              onDeleteThread={async (threadId) => {
                if (threadId === chat.activeThreadId) closeInspect()
                await chat.removeThread(threadId)
              }}
              onTitleAnimationComplete={chat.finishTitleAnimation}
              runStates={chat.runStates}
              unreadThreadIds={chat.unreadThreadIds}
              actions={[
                {
                  key: "plugins",
                  label: intl.formatMessage({
                    id: "dashboard_sidebar_plugins_button",
                    defaultMessage: "Plugins",
                  }),
                  icon: UnplugIcon,
                  badge: intl.formatMessage({
                    id: "dashboard_sidebar_plugins_soon_label",
                    defaultMessage: "Coming soon",
                  }),
                  // TODO: open the plugins panel once it exists.
                  onClick: () =>
                    toast.info(
                      intl.formatMessage({
                        id: "dashboard_plugins_soon_toast",
                        defaultMessage: "Plugins are coming soon",
                      }),
                      {
                        description: intl.formatMessage({
                          id: "dashboard_plugins_soon_body",
                          defaultMessage:
                            "Connect external tools to extend what SurfSense can do. We’re still polishing this.",
                        }),
                      }
                    ),
                },
              ]}
              sources={
                <aside
                  id={LEFT_SOURCES_ID}
                  aria-label={intl.formatMessage({
                    id: "dashboard_sources_aria",
                    defaultMessage: "Workspace sources",
                  })}
                  className="flex h-full min-h-0 min-w-0 flex-col"
                >
                  <SourcesPanel
                    documents={sources.documents}
                    index={sources.index}
                    selectedDocumentIds={sources.includedDocumentIds}
                    folderTicks={sources.folderTicks}
                    highlightedDocumentId={null}
                    isLoading={sources.isLoading}
                    isDeleting={sources.isDeleting}
                    error={sources.error}
                    upload={{
                      isUploading: sources.isUploading,
                      onUpload: (files) => void sources.upload(files),
                      onUploadFolder: (entries) =>
                        void sources.uploadEntries(entries),
                    }}
                    onDropFiles={
                      sources.isUploading
                        ? undefined
                        : (entries, folderId) =>
                            void sources.uploadEntries(entries, folderId)
                    }
                    onOpen={(id) => void sources.openOriginal(id)}
                    onPreview={toggleSourcePreview}
                    onReveal={(id) => void sources.revealOriginal(id)}
                    onRetry={(id) => void sources.retry(id)}
                    onCancel={(id) => void sources.cancel(id)}
                    onDelete={(id) => void sources.deleteOne(id)}
                    onDeleteSelected={() => void sources.deleteSelected()}
                    onSelectionChange={sources.setDocumentIncluded}
                    onFolderSelectionChange={sources.setFolderIncluded}
                    onToggleAll={sources.toggleAllIncluded}
                    onRename={sources.rename}
                    folderActions={sources.folderActions}
                    notes={{
                      write: sources.writeNote,
                      load: sources.loadNote,
                      edit: sources.editNote,
                    }}
                  />
                </aside>
              }
              footer={<SidebarFooter onOpenLicense={onOpenLicense} />}
            />
          </div>
        </div>
        <div className="flex min-h-0 min-w-[520px] flex-1 flex-col">
          <ApprovalDialog
            request={chat.approvals[0] ?? null}
            othersWaiting={Math.max(0, chat.approvals.length - 1)}
            onAnswer={chat.answerApproval}
          />
          <ThreadPanel
            runtime={chat.runtime}
            thread={chat.activeThread}
            view={chat.conversationView}
            model={selection}
            isLoading={chat.isLoadingMessages}
            isRunning={chat.isRunning}
            animateTitle={chat.activeThreadId === chat.animatingTitleThreadId}
            providerAvailable={providerAvailable}
            notice={
              modelIssue ? (
                <ModelIssueNotice
                  issue={modelIssue}
                  onAllow={needsConsent ? onAllowModelIssue : undefined}
                  onOpenSettings={onModelIssueSettings}
                />
              ) : null
            }
            blockedPlaceholder={composerHold}
            onCitation={(chunkId) => {
              openRightPanel()
              setInspect({ kind: "citation", chunkId })
            }}
            onModelSetup={onModelRequired}
            onModelSelected={onModelSelected}
            onRetry={chat.retry}
            onNewChat={startNewChat}
            sourceCount={sources.includedDocumentIds.length}
            onUploadSources={(files) => void sources.upload(files)}
            isUploadingSources={sources.isUploading}
            onTitleAnimationComplete={chat.finishTitleAnimation}
            autoNamingThreadId={chat.autoNamingThreadId}
            onRename={chat.rename}
            onDelete={async (threadId) => {
              if (threadId === chat.activeThreadId) closeInspect()
              await chat.removeThread(threadId)
            }}
          />
        </div>
        <SlideRail
          open={rightPanelOpen}
          side="end"
          width={inspect ? DETAIL_RAIL_WIDTH : MAIN_RAIL_WIDTH}
        >
          <div id="workspace-right-panel" className="h-full min-h-0">
            <RightPanel
              inspect={
                inspect?.kind === "citation" ? (
                  <CitationPanel
                    workspaceId={workspace.id}
                    chunkId={inspect.chunkId}
                    onClose={closeInspect}
                    onOpen={(id) => void sources.openOriginal(id)}
                  />
                ) : inspect?.kind === "artifact" ? (
                  <ArtifactPanel
                    artifactId={inspect.artifactId}
                    artifacts={studio.artifacts}
                    onOpenVersion={openArtifact}
                    onRefine={studio.refine}
                    onDecideAll={studio.decideAll}
                    onClose={closeInspect}
                  />
                ) : null
              }
              studio={
                <StudioPanel
                  workspaceId={workspace.id}
                  documents={sources.documents}
                  selectedDocumentIds={sources.includedDocumentIds}
                  sourceScope={sources.sourceScope}
                  onSelectionChange={sources.setDocumentIncluded}
                  onToggleAll={sources.toggleAllIncluded}
                  formats={studio.formats}
                  isCreating={studio.isCreating}
                  error={studio.error}
                  onGenerate={studio.create}
                  onSetUpVoices={onOpenAudioSettings}
                />
              }
              artifacts={
                <ArtifactList
                  workspaceId={workspace.id}
                  artifacts={studio.artifacts}
                  formats={studio.formats}
                  isLoading={studio.isLoading}
                  onOpen={openArtifact}
                  onRegenerate={(artifactId) =>
                    void studio.regenerate(artifactId)
                  }
                  onCancel={(artifactId) => void studio.cancel(artifactId)}
                  onDelete={(artifactId) => void studio.remove(artifactId)}
                />
              }
            />
          </div>
        </SlideRail>
      </section>
    </OpenArtifactContext.Provider>
  )
}

function WorkspacesEmpty({
  isMutating,
  onCreate,
  onImported,
}: {
  isMutating: boolean
  onCreate: (name: string) => Promise<boolean>
  onImported: (accepted: ImportAccepted) => Promise<void>
}) {
  return (
    <main className="flex h-full items-center justify-center bg-background p-8">
      <div className="flex max-w-sm flex-col items-center text-center">
        <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-muted">
          <LayoutGridIcon className="size-5" />
        </div>
        <h1 className="font-heading text-xl font-medium">
          {intl.formatMessage({
            id: "dashboard_workspaces_empty",
            defaultMessage: "No workspaces",
          })}
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {intl.formatMessage({
            id: "dashboard_workspaces_empty_body",
            defaultMessage:
              "A workspace keeps a source library and its chats together.",
          })}
        </p>
        <Button
          className="mt-5"
          disabled={isMutating}
          onClick={() =>
            void onCreate(
              intl.formatMessage({
                id: "dashboard_workspaces_default_name_label",
                defaultMessage: "My Workspace",
              })
            )
          }
        >
          <PlusIcon />
          {intl.formatMessage({
            id: "dashboard_workspaces_create_button",
            defaultMessage: "Create workspace",
          })}
        </Button>
        <div className="mt-3">
          <ImportBundleButton onImported={onImported} />
        </div>
      </div>
    </main>
  )
}

export function DashboardPage({
  selection,
  initialProviderAvailable = false,
  initialAvailability,
  initialWorkspaces,
  onModelUnavailable = () => undefined,
  onModelSelected,
}: {
  selection: ModelSelection | null
  // Shorthand for an `available` or unchecked initial status.
  initialProviderAvailable?: boolean
  // What startup found, so this screen need not check the same model again.
  initialAvailability?: Availability
  initialWorkspaces: Workspace[]
  onModelUnavailable?: () => void
  onModelSelected: (selection: ModelSelection) => void
}) {
  const workspaces = useWorkspaces(initialWorkspaces)
  const initial: Availability =
    initialAvailability ??
    (initialProviderAvailable
      ? { status: "available" }
      : { status: "checking" })
  // Tagged with the model it describes, so a newly chosen model reads as
  // checking until its own answer arrives, never as the last one's.
  const [checked, setChecked] = useState<{
    key: string | null
    availability: Availability
  }>(() => ({
    key: selection ? modelKey(selection) : null,
    availability: initial,
  }))
  // Startup already checked this model; the first run here would repeat it.
  const skipFirstCheck = useRef(initial.status !== "checking")
  const [settingsOpen, setSettingsOpen] = useState(false)
  // Bumped when the settings dialog closes, because a model can be chosen in
  // there without anything on this screen hearing about it: the image model is
  // selected inside the catalog and never reaches `onModelSelected`.
  const [modelsVisited, setModelsVisited] = useState(0)
  const [settingsSection, setSettingsSection] =
    useState<SettingsSectionId>("general")
  // Bumped after egress is allowed from the notice, to check the model again.
  const [consents, setConsents] = useState(0)

  const openSettings = (section: SettingsSectionId) => {
    setSettingsSection(section)
    setSettingsOpen(true)
  }
  // The menu has Settings to go to here, once a workspace renders it;
  // otherwise it opens the dialog.
  useHelpMenuReport(
    () => openSettings("report-issue"),
    Boolean(workspaces.activeWorkspace)
  )

  // Checked when the model changes, when settings close (a key entered again,
  // egress switched, a connection edited) and after egress is allowed.
  useEffect(() => {
    if (!selection) return
    if (skipFirstCheck.current) {
      skipFirstCheck.current = false
      return
    }
    const key = modelKey(selection)
    const controller = new AbortController()
    void checkAvailability(selection, controller.signal).then(
      (availability) => {
        if (!controller.signal.aborted) setChecked({ key, availability })
      }
    )
    return () => controller.abort()
  }, [selection, modelsVisited, consents])

  const availability: Availability =
    selection && checked.key === modelKey(selection)
      ? checked.availability
      : { status: "checking" }
  const issue =
    availability.status === "needs-consent" ||
    availability.status === "unusable"
      ? availability.issue
      : null
  // A model gone from its list is set up again from scratch.
  const usableSelection = availability.status === "gone" ? null : selection
  const providerAvailable =
    usableSelection !== null && availability.status !== "unusable"

  const allowModelIssue = () => {
    const destination = issue?.destination
    if (!destination) return
    void askEgress({
      destination,
      host: issue.host ?? "",
      allow: () => setDestinationEnabled(destination, true),
    }).then((allowed) => {
      if (allowed) setConsents((count) => count + 1)
    })
  }

  const onImported = async (accepted: ImportAccepted) => {
    const first = accepted.workspaces[0]
    await workspaces.reload(first?.id ?? workspaces.activeWorkspace?.id ?? -1)
  }

  if (!workspaces.activeWorkspace) {
    return (
      <WorkspacesEmpty
        isMutating={workspaces.isMutating}
        onCreate={workspaces.create}
        onImported={onImported}
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
        selection={usableSelection}
        providerAvailable={providerAvailable}
        modelIssue={issue}
        needsConsent={availability.status === "needs-consent"}
        onAllowModelIssue={allowModelIssue}
        onModelIssueSettings={() =>
          openSettings(
            availability.status === "needs-consent" ? "network" : "chat-models"
          )
        }
        onModelRequired={() => openSettings("chat-models")}
        onModelSelected={onModelSelected}
        onOpenLicense={() => openSettings("license")}
        onOpenAudioSettings={() => openSettings("audio-models")}
        modelsVisited={modelsVisited}
      />
      <SettingsDialog
        open={settingsOpen}
        section={settingsSection}
        onOpenChange={(open) => {
          setSettingsOpen(open)
          if (!open) {
            setModelsVisited((seen) => seen + 1)
          }
        }}
        onSectionChange={setSettingsSection}
        onModelUnavailable={onModelUnavailable}
        onModelSelected={onModelSelected}
        onImported={onImported}
      />
      {workspaces.error ? (
        <Alert
          variant="destructive"
          className="absolute top-4 left-1/2 z-40 w-auto max-w-lg -translate-x-1/2 shadow-lg"
        >
          <CircleAlertIcon />
          <AlertTitle>
            {intl.formatMessage({
              id: "dashboard_workspace_error_title",
              defaultMessage: "Workspace action failed",
            })}
          </AlertTitle>
          <AlertDescription>{workspaces.error}</AlertDescription>
          <Button
            variant="ghost"
            size="icon-sm"
            className="absolute top-1 right-1"
            aria-label={intl.formatMessage({
              id: "dashboard_workspace_error_dismiss_aria",
              defaultMessage: "Dismiss workspace error",
            })}
            onClick={workspaces.clearError}
          >
            <XIcon />
          </Button>
        </Alert>
      ) : null}
    </main>
  )
}
