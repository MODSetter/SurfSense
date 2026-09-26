import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import {
  BugIcon,
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
import { openIssueReport } from "@/features/feedback/issue-report-state"
import { ModelIssueNotice } from "@/features/chat/model-issue-notice"
import { ThreadPanel } from "@/features/chat/thread-panel"
import { useChatRuntime } from "@/features/chat/use-chat-runtime"
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
import {
  SourcesAddButton,
  SourcesPanel,
} from "@/features/sources/sources-panel"
import { useSources } from "@/features/sources/use-sources"
import { ArtifactList } from "@/features/studio/artifact-list"
import { ArtifactPanel } from "@/features/studio/artifact-panel"
import { StudioPanel } from "@/features/studio/studio-panel"
import { useStudio } from "@/features/studio/use-studio"
import { UpdateButton } from "@/features/updates/update-settings"
import type { Workspace } from "@/features/workspaces/api"
import { useWorkspaces } from "@/features/workspaces/use-workspaces"
import { intl } from "@/i18n/intl"
import { WorkspaceRail } from "@/features/workspaces/workspace-rail"
import { readRightPanelOpen, writeRightPanelOpen } from "./chrome-prefs"
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
  modelsVisited: number
}) {
  const [inspect, setInspect] = useState<Inspect>(null)
  const [rightPanelOpen, setRightPanelOpen] = useState(readRightPanelOpen)
  const sources = useSources(workspace.id)
  // Which formats Studio offers is the server's answer to what is selected,
  // so it has to be asked again when that changes. The chat model is named
  // here directly; the image model is chosen inside the settings dialog and
  // reported only by `modelsVisited`, which counts closing it.
  const studio = useStudio(
    workspace.id,
    `${selection ? modelKey(selection) : "none"}:${modelsVisited}`
  )
  const chat = useChatRuntime({
    workspaceId: workspace.id,
    canSend: providerAvailable,
    selectedDocumentIds: sources.includedDocumentIds,
    onModelRequired,
  })

  const composerHold =
    modelIssue && needsConsent ? consentPlaceholder(modelIssue) : undefined

  const closeInspect = () => setInspect(null)
  const toggleRightPanel = () => {
    setRightPanelOpen((open) => {
      const next = !open
      writeRightPanelOpen(next)
      return next
    })
  }
  const openRightPanel = () => {
    setRightPanelOpen(true)
    writeRightPanelOpen(true)
  }
  return (
    <>
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
        <div className="flex h-full min-h-0 w-68 min-w-58 shrink-0 flex-col">
          <LeftSidebar
            threads={chat.threads}
            activeThreadId={chat.activeThreadId}
            autoNamingThreadId={chat.autoNamingThreadId}
            animatingTitleThreadId={chat.animatingTitleThreadId}
            isLoadingThreads={chat.isLoadingThreads}
            onNewChat={() => {
              closeInspect()
              chat.startNewChat()
            }}
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
              {
                key: "report-issue",
                label: intl.formatMessage({
                  id: "dashboard_sidebar_report_issue_button",
                  defaultMessage: "Report issue",
                }),
                icon: BugIcon,
                onClick: () => openIssueReport(),
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
                  selectedDocumentIds={sources.includedDocumentIds}
                  highlightedDocumentId={null}
                  isLoading={sources.isLoading}
                  isDeleting={sources.isDeleting}
                  error={sources.error}
                  addAction={
                    <SourcesAddButton
                      isUploading={sources.isUploading}
                      onUpload={(files) => void sources.upload(files)}
                    />
                  }
                  onOpen={(id) => void sources.openOriginal(id)}
                  onReveal={(id) => void sources.revealOriginal(id)}
                  onRetry={(id) => void sources.retry(id)}
                  onCancel={(id) => void sources.cancel(id)}
                  onDelete={(id) => void sources.deleteOne(id)}
                  onDeleteSelected={() => void sources.deleteSelected()}
                  onSelectionChange={sources.setDocumentIncluded}
                  onToggleAll={sources.toggleAllIncluded}
                />
              </aside>
            }
            footer={<SidebarFooter onOpenLicense={onOpenLicense} />}
          />
        </div>
        <div className="flex min-h-0 min-w-[520px] flex-1 flex-col">
          <ThreadPanel
            runtime={chat.runtime}
            thread={chat.activeThread}
            view={chat.conversationView}
            model={selection}
            isLoading={chat.isLoadingMessages}
            isRunning={chat.isRunning}
            isUploading={sources.isUploading}
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
            onUpload={(files) => void sources.upload(files)}
            sourceCount={sources.includedDocumentIds.length}
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
                    onClose={closeInspect}
                  />
                ) : null
              }
              studio={
                <StudioPanel
                  workspaceId={workspace.id}
                  documents={sources.documents}
                  selectedDocumentIds={sources.includedDocumentIds}
                  onSelectionChange={sources.setDocumentIncluded}
                  onToggleAll={sources.toggleAllIncluded}
                  formats={studio.formats}
                  isCreating={studio.isCreating}
                  error={studio.error}
                  onGenerate={studio.create}
                />
              }
              artifacts={
                <ArtifactList
                  workspaceId={workspace.id}
                  artifacts={studio.artifacts}
                  formats={studio.formats}
                  isLoading={studio.isLoading}
                  onOpen={(artifactId) => {
                    openRightPanel()
                    setInspect({ kind: "artifact", artifactId })
                  }}
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
    </>
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
