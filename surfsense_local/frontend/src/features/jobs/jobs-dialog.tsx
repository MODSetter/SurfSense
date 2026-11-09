import { memo, useState } from "react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { useLicense } from "@/features/license/use-license"
import type { ModelSelection } from "@/features/models/selection/api"
import type { WorkspaceDocument } from "@/features/sources/api"
import { useOpenArtifact } from "@/features/studio/open-artifact"
import { intl } from "@/i18n/intl"

import { jobRunnerOfKey } from "./catalog"
import { JobList } from "./job-list"
import { ContractRunForm } from "./run/contract-run-form"
import { JobRunForm } from "./run/job-run-form"
import { JobRunProgress } from "./run/job-run-progress"
import { WORD_CLAUSES } from "./runners"
import { JobSettingsForm } from "./settings/job-settings-form"
import { useJobPacks } from "./use-job-packs"

export type JobsView =
  | { name: "list" }
  | { name: "run"; job: string; title: string }
  | { name: "progress"; runId: number }
  | { name: "settings"; job: string; title: string }

export type JobsDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: number
  documents: readonly WorkspaceDocument[]
  // Ready sources ticked in the sidebar, which a run starts from.
  includedDocumentIds: readonly number[]
  // The chat model a run answers with; null when none is usable.
  selection: ModelSelection | null
  providerAvailable: boolean
  onUploadSources: (files: File[]) => unknown
  onOpenModelSettings: (section: "chat-models") => void
  onOpenLicense: () => void
}

const LIST: JobsView = { name: "list" }

// Job screens name the firm a Business license is for (ADR 0080).
function JobsHeader() {
  const firm = useLicense().data?.firm?.trim()
  return (
    <DialogHeader>
      <DialogTitle className="text-xl">
        {intl.formatMessage({
          id: "jobs_dialog_title",
          defaultMessage: "Jobs",
        })}
      </DialogTitle>
      <DialogDescription className="text-pretty">
        {intl.formatMessage({
          id: "jobs_dialog_body",
          defaultMessage:
            "Jobs fill in paperwork from your firm’s own documents. Each run makes a copy in Studio, so your file is never changed.",
        })}
      </DialogDescription>
      {firm ? (
        <p className="text-sm text-muted-foreground">
          {intl.formatMessage(
            {
              id: "jobs_dialog_firm_label",
              defaultMessage: "Licensed to {firm}",
            },
            { firm }
          )}
        </p>
      ) : null}
    </DialogHeader>
  )
}

/**
 * The workspace's jobs: the list with recent runs, a run's form, one run, and
 * a job's settings. Its content mounts only while open, so nothing here is read
 * before Jobs is.
 */
export const JobsDialog = memo(function JobsDialog({
  open,
  onOpenChange,
  workspaceId,
  documents,
  includedDocumentIds,
  selection,
  providerAvailable,
  onUploadSources,
  onOpenModelSettings,
  onOpenLicense,
}: JobsDialogProps) {
  const [view, setView] = useState<JobsView>(LIST)
  const openArtifact = useOpenArtifact()
  const packs = useJobPacks().data
  // Jobs closes first, so two modal roots never stack.
  const leaveFor = (next: () => void) => {
    onOpenChange(false)
    next()
  }
  const toList = () => setView(LIST)

  let content
  switch (view.name) {
    case "list":
      content = (
        <JobList
          workspaceId={workspaceId}
          onRun={(job, title) => setView({ name: "run", job, title })}
          onSettings={(job, title) => setView({ name: "settings", job, title })}
          onOpenRun={(runId) => setView({ name: "progress", runId })}
          onOpenLicense={() => leaveFor(onOpenLicense)}
        />
      )
      break
    case "run": {
      // Each runner works on its own kind of file, so has its own form.
      const RunForm =
        jobRunnerOfKey(view.job, packs) === WORD_CLAUSES
          ? ContractRunForm
          : JobRunForm
      content = (
        <RunForm
          key={view.job}
          workspaceId={workspaceId}
          job={view.job}
          title={view.title}
          documents={documents}
          includedDocumentIds={includedDocumentIds}
          selection={selection}
          providerAvailable={providerAvailable}
          onUploadSources={onUploadSources}
          onChooseModel={() =>
            leaveFor(() => onOpenModelSettings("chat-models"))
          }
          onStarted={(runId) => setView({ name: "progress", runId })}
          onBack={toList}
        />
      )
      break
    }
    case "progress":
      content = (
        <JobRunProgress
          key={view.runId}
          workspaceId={workspaceId}
          runId={view.runId}
          onOpenInStudio={(artifactId) =>
            leaveFor(() => openArtifact?.(artifactId))
          }
          onChooseFile={(job, title) => setView({ name: "run", job, title })}
          onBack={toList}
        />
      )
      break
    case "settings":
      content = (
        <JobSettingsForm
          key={view.job}
          job={view.job}
          title={view.title}
          onBack={toList}
        />
      )
      break
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => onOpenChange(next)}
      onOpenChangeComplete={(isOpen) => {
        if (!isOpen) setView(LIST)
      }}
    >
      <DialogContent className="select-none sm:max-w-2xl">
        <JobsHeader />
        {/* Keyed by view, so each opens at its top. */}
        <ScrollFade
          key={view.name}
          className="h-128 min-w-0"
          viewportClassName="overflow-x-hidden pr-2"
        >
          {content}
        </ScrollFade>
      </DialogContent>
    </Dialog>
  )
})
