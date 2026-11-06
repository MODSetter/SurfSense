import { useId, useRef, useState, type ChangeEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { PlusIcon, Upload01Icon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { useChatCandidates } from "@/features/models/chat-candidates/use-chat-candidates"
import type { ModelSelection } from "@/features/models/selection/api"
import {
  SOURCE_FILE_ACCEPT,
  type WorkspaceDocument,
} from "@/features/sources/api"
import { SourceChecklist } from "@/features/sources/source-checklist"
import { studioKeys } from "@/features/studio/query-keys"
import { intl } from "@/i18n/intl"

import { AllJobsButton } from "../all-jobs-button"
import { startJobRun, type JobRunStart } from "../api"
import { jobsErrorText } from "../job-error-text"
import { jobsKeys } from "../query-keys"
import { useJobSettings } from "../settings/use-job-settings"

import { displayModelName } from "./model-display-name"
import {
  chosenPolicies,
  defaultWorkbook,
  policyChoices,
  sourcesReading,
  workbookChoices,
  workbooksReading,
} from "./run-sources"
import { WorkbookPicker } from "./workbook-picker"

// The provider that runs models on this computer; any other sends them the
// questions and passages.
const LOCAL_RUNTIME = "llamacpp"

const filesOf = (event: ChangeEvent<HTMLInputElement>) => {
  const files = Array.from(event.target.files ?? [])
  event.target.value = ""
  return files
}

/**
 * A run's workbook and the documents it answers from, started on the chat
 * model the app has selected, which the worker resolves again when the run
 * begins.
 */
export function JobRunForm({
  workspaceId,
  job,
  title,
  documents,
  includedDocumentIds,
  selection,
  providerAvailable,
  onUploadSources,
  onChooseModel,
  onStarted,
  onBack,
}: {
  workspaceId: number
  // The installed job's key, which the run sends.
  job: string
  title: string
  documents: readonly WorkspaceDocument[]
  includedDocumentIds: readonly number[]
  selection: ModelSelection | null
  providerAvailable: boolean
  onUploadSources: (files: File[]) => unknown
  onChooseModel: () => void
  onStarted: (runId: number) => void
  onBack: () => void
}) {
  const queryClient = useQueryClient()
  const candidates = useChatCandidates().data
  const checker = useJobSettings(job).data?.checker ?? null
  const workbookLabel = useId()
  const policiesLabel = useId()
  const workbookInput = useRef<HTMLInputElement>(null)
  const policiesInput = useRef<HTMLInputElement>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [marks, setMarks] = useState<ReadonlyMap<number, boolean>>(new Map())

  const workbooks = workbookChoices(documents)
  // Derived, so a workbook that becomes ready while the form is open is chosen.
  const workbookId = workbooks.some((each) => each.id === picked)
    ? picked
    : defaultWorkbook(workbooks, includedDocumentIds)
  const policies = policyChoices(documents, workbookId)
  const chosen = chosenPolicies(policies, marks, includedDocumentIds)
  const readingWorkbooks = workbooksReading(documents)
  const readingSources = sourcesReading(documents)

  const start = useMutation({
    mutationFn: (run: JobRunStart) => startJobRun(workspaceId, run),
    onSuccess: ({ artifact_id }) => {
      // The route answers only the id, so Studio's list is read again to show the copy.
      void queryClient.invalidateQueries({
        queryKey: studioKeys.artifacts(workspaceId),
      })
      void queryClient.invalidateQueries({
        queryKey: jobsKeys.runs(workspaceId),
      })
      onStarted(artifact_id)
    },
  })
  const busy = start.isPending

  const mark = (documentId: number, on: boolean) =>
    setMarks((current) => new Map(current).set(documentId, on))
  const everyChosen = policies.length > 0 && chosen.length === policies.length
  const markAll = () =>
    setMarks(
      (current) =>
        new Map([
          ...current,
          ...policies.map((policy) => [policy.id, !everyChosen] as const),
        ])
    )

  const answering = selection
    ? displayModelName(selection.name, candidates)
    : null
  const usable = selection !== null && providerAvailable
  const remote =
    (usable && selection.provider !== LOCAL_RUNTIME) ||
    (checker !== null && checker.provider !== LOCAL_RUNTIME)
  const canStart = workbookId !== null && chosen.length > 0 && usable && !busy

  const chooseModelButton = (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="self-start"
      disabled={busy}
      onClick={onChooseModel}
    >
      {intl.formatMessage({
        id: "jobs_run_model_choose_button",
        defaultMessage: "Choose a model",
      })}
    </Button>
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <AllJobsButton onClick={onBack} disabled={busy} />
        <h3 className="text-base font-medium text-balance">
          {intl.formatMessage(
            { id: "jobs_run_title", defaultMessage: "Run {job}" },
            { job: title }
          )}
        </h3>
      </div>

      <section className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h4 id={workbookLabel} className="text-sm font-medium">
              {intl.formatMessage({
                id: "jobs_run_workbook_label",
                defaultMessage: "Workbook to fill in",
              })}
            </h4>
            <p className="text-sm text-pretty text-muted-foreground">
              {intl.formatMessage({
                id: "jobs_run_workbook_body",
                defaultMessage:
                  "The questionnaire you received, as an Excel file (.xlsx). Each run fills in one workbook: SurfSense fills in a copy and leaves your file as it is.",
              })}
            </p>
          </div>
          {/* With none, the empty state below carries its own button. */}
          {workbooks.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="shrink-0 text-muted-foreground"
              disabled={busy}
              onClick={() => workbookInput.current?.click()}
            >
              <PlusIcon data-icon="inline-start" />
              {intl.formatMessage({
                id: "jobs_run_workbook_add_another_button",
                defaultMessage: "Add a workbook",
              })}
            </Button>
          ) : null}
        </div>
        <Input
          ref={workbookInput}
          type="file"
          accept=".xlsx"
          className="sr-only"
          aria-label={intl.formatMessage({
            id: "jobs_run_workbook_file_aria",
            defaultMessage: "Choose a workbook to add",
          })}
          disabled={busy}
          onChange={(event) => {
            const [file] = filesOf(event)
            if (file) onUploadSources([file])
          }}
        />
        {workbooks.length > 0 ? (
          <WorkbookPicker
            labelledBy={workbookLabel}
            workbooks={workbooks}
            value={workbookId}
            onChange={setPicked}
            disabled={busy}
          />
        ) : (
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-pretty text-muted-foreground">
              {intl.formatMessage({
                id: "jobs_run_workbook_empty",
                defaultMessage:
                  "None of this workspace’s sources is an Excel workbook (.xlsx). Add the questionnaire you received. Save a Word or older Excel file as .xlsx first.",
              })}
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => workbookInput.current?.click()}
            >
              <Upload01Icon data-icon="inline-start" />
              {intl.formatMessage({
                id: "jobs_run_workbook_add_button",
                defaultMessage: "Add a workbook",
              })}
            </Button>
          </div>
        )}
        {readingWorkbooks > 0 ? (
          <p role="status" className="text-sm text-muted-foreground">
            {intl.formatMessage(
              {
                id: "jobs_run_workbook_reading_status",
                defaultMessage:
                  "{count, plural, one {# workbook is} other {# workbooks are}} still being read.",
              },
              { count: readingWorkbooks }
            )}
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h4 id={policiesLabel} className="text-sm font-medium">
              {intl.formatMessage({
                id: "jobs_run_policies_label",
                defaultMessage: "Your firm’s documents to answer from",
              })}
            </h4>
            <p className="text-sm text-pretty text-muted-foreground">
              {intl.formatMessage({
                id: "jobs_run_policies_body",
                defaultMessage:
                  "Policies, procedures and other documents the answers should rest on. The sources ticked in the sidebar are chosen to start with, except other workbooks.",
              })}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {policies.length > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="xs"
                className="text-muted-foreground"
                disabled={busy}
                onClick={markAll}
              >
                {everyChosen
                  ? intl.formatMessage({
                      id: "jobs_run_policies_deselect_all_button",
                      defaultMessage: "Deselect all",
                    })
                  : intl.formatMessage({
                      id: "jobs_run_policies_select_all_button",
                      defaultMessage: "Select all",
                    })}
              </Button>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="text-muted-foreground"
              disabled={busy}
              onClick={() => policiesInput.current?.click()}
            >
              <PlusIcon data-icon="inline-start" />
              {intl.formatMessage({
                id: "jobs_run_policies_add_button",
                defaultMessage: "Add documents",
              })}
            </Button>
          </div>
        </div>
        <Input
          ref={policiesInput}
          type="file"
          multiple
          accept={SOURCE_FILE_ACCEPT}
          className="sr-only"
          aria-label={intl.formatMessage({
            id: "jobs_run_policies_file_aria",
            defaultMessage: "Choose documents to add",
          })}
          disabled={busy}
          onChange={(event) => {
            const files = filesOf(event)
            if (files.length > 0) onUploadSources(files)
          }}
        />
        {policies.length > 0 ? (
          <>
            <div role="group" aria-labelledby={policiesLabel}>
              <SourceChecklist
                documents={policies}
                isChecked={(documentId) => chosen.includes(documentId)}
                onToggle={mark}
                disabled={busy}
              />
            </div>
            {chosen.length > 0 ? (
              <p className="text-sm text-muted-foreground">
                {intl.formatMessage(
                  {
                    id: "jobs_run_policies_count_label",
                    defaultMessage:
                      "{count, plural, =0 {None chosen} one {# document chosen} other {# documents chosen}}",
                  },
                  { count: chosen.length }
                )}
              </p>
            ) : (
              <p role="status" className="text-sm text-muted-foreground">
                {intl.formatMessage({
                  id: "jobs_run_policies_none_status",
                  defaultMessage:
                    "Choose at least one document to answer from.",
                })}
              </p>
            )}
          </>
        ) : (
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "jobs_run_policies_empty",
              defaultMessage:
                "No other source is ready to answer from. Add your firm’s policies first.",
            })}
          </p>
        )}
        {readingSources > 0 ? (
          <p role="status" className="text-sm text-muted-foreground">
            {intl.formatMessage(
              {
                id: "jobs_run_policies_reading_status",
                defaultMessage:
                  "{count, plural, one {# source is} other {# sources are}} still being read, and can be chosen once ready.",
              },
              { count: readingSources }
            )}
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-1.5 text-sm">
        {selection === null ? (
          <>
            <p className="text-pretty">
              {intl.formatMessage({
                id: "jobs_run_model_missing_body",
                defaultMessage:
                  "Choose a chat model first. It answers the questions.",
              })}
            </p>
            {chooseModelButton}
          </>
        ) : !providerAvailable ? (
          <>
            <p className="text-pretty">
              {intl.formatMessage(
                {
                  id: "jobs_run_model_unusable_body",
                  defaultMessage:
                    "{model} can’t be reached right now. Check it in Settings, or choose another.",
                },
                { model: answering }
              )}
            </p>
            {chooseModelButton}
          </>
        ) : (
          <p>
            {intl.formatMessage(
              {
                id: "jobs_run_model_label",
                defaultMessage: "Answered by {model}",
              },
              { model: answering }
            )}
          </p>
        )}
        {checker ? (
          <p>
            {intl.formatMessage(
              {
                id: "jobs_run_checker_label",
                defaultMessage: "Checked again by {model}",
              },
              { model: displayModelName(checker.name, candidates) }
            )}
          </p>
        ) : null}
        {usable && selection.provider === LOCAL_RUNTIME ? (
          <p className="text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "jobs_run_model_local_body",
              defaultMessage:
                "Models that run on this computer are usually smaller, and leave more questions for a person to answer.",
            })}
          </p>
        ) : null}
        {remote ? (
          <p className="text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "jobs_run_remote_body",
              defaultMessage:
                "Models that don’t run on this computer receive the questions and passages from your documents.",
            })}
          </p>
        ) : null}
      </section>

      {start.error ? (
        <p role="alert" className="text-sm text-pretty text-destructive">
          {jobsErrorText(start.error)}
        </p>
      ) : null}

      <div className="flex justify-end">
        <Button
          type="button"
          disabled={!canStart}
          onClick={() => {
            if (workbookId === null) return
            start.mutate({ job, document_id: workbookId, source_ids: chosen })
          }}
        >
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {busy
            ? intl.formatMessage({
                id: "jobs_run_starting_status",
                defaultMessage: "Starting…",
              })
            : intl.formatMessage({
                id: "jobs_run_start_button",
                defaultMessage: "Start",
              })}
        </Button>
      </div>
    </div>
  )
}
