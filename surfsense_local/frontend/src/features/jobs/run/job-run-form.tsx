import { useState } from "react"

import { intl } from "@/i18n/intl"

import { EvidenceChecklist } from "./evidence-checklist"
import { RunFileSection } from "./run-file-section"
import type { RunFormProps } from "./run-form-props"
import { RunFormHeader } from "./run-form-header"
import { RunModelLines } from "./run-model-lines"
import {
  chosenPolicies,
  defaultWorkbook,
  policyChoices,
  sourcesReading,
  workbookChoices,
  workbooksReading,
} from "./run-sources"
import { StartRunButton } from "./start-run-button"
import { useSourceMarks } from "./use-source-marks"
import { useStartRun } from "./use-start-run"

/** A run's workbook and the documents it answers from. */
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
}: RunFormProps) {
  const [picked, setPicked] = useState<number | null>(null)
  const [marks, mark] = useSourceMarks()
  const start = useStartRun(workspaceId, onStarted)
  const busy = start.isPending

  const workbooks = workbookChoices(documents)
  // Derived, so a workbook that becomes ready while the form is open is chosen.
  const workbookId = workbooks.some((each) => each.id === picked)
    ? picked
    : defaultWorkbook(workbooks, includedDocumentIds)
  const policies = policyChoices(documents, workbookId)
  const chosen = chosenPolicies(policies, marks, includedDocumentIds)
  const usable = selection !== null && providerAvailable
  const canStart = workbookId !== null && chosen.length > 0 && usable && !busy

  return (
    <div className="flex flex-col gap-6">
      <RunFormHeader title={title} busy={busy} onBack={onBack} />
      <RunFileSection
        files={workbooks}
        value={workbookId}
        onChange={setPicked}
        reading={workbooksReading(documents)}
        accept=".xlsx"
        busy={busy}
        onUpload={onUploadSources}
        text={{
          label: intl.formatMessage({
            id: "jobs_run_workbook_label",
            defaultMessage: "Workbook to fill in",
          }),
          body: intl.formatMessage({
            id: "jobs_run_workbook_body",
            defaultMessage:
              "The questionnaire you received, as an Excel file (.xlsx). Each run fills in one workbook: SurfSense fills in a copy and leaves your file as it is.",
          }),
          addAnother: intl.formatMessage({
            id: "jobs_run_workbook_add_another_button",
            defaultMessage: "Add a workbook",
          }),
          fileAria: intl.formatMessage({
            id: "jobs_run_workbook_file_aria",
            defaultMessage: "Choose a workbook to add",
          }),
          empty: intl.formatMessage({
            id: "jobs_run_workbook_empty",
            defaultMessage:
              "None of this workspace’s sources is an Excel workbook (.xlsx). Add the questionnaire you received. Save a Word or older Excel file as .xlsx first.",
          }),
          add: intl.formatMessage({
            id: "jobs_run_workbook_add_button",
            defaultMessage: "Add a workbook",
          }),
          reading: (count) =>
            intl.formatMessage(
              {
                id: "jobs_run_workbook_reading_status",
                defaultMessage:
                  "{count, plural, one {# workbook is} other {# workbooks are}} still being read.",
              },
              { count }
            ),
        }}
      />
      <EvidenceChecklist
        choices={policies}
        chosen={chosen}
        onMark={mark}
        reading={sourcesReading(documents)}
        busy={busy}
        onUpload={onUploadSources}
        text={{
          label: intl.formatMessage({
            id: "jobs_run_policies_label",
            defaultMessage: "Your firm’s documents to answer from",
          }),
          body: intl.formatMessage({
            id: "jobs_run_policies_body",
            defaultMessage:
              "Policies, procedures and other documents the answers should rest on. The sources ticked in the sidebar are chosen to start with, except other workbooks.",
          }),
          add: intl.formatMessage({
            id: "jobs_run_policies_add_button",
            defaultMessage: "Add documents",
          }),
          fileAria: intl.formatMessage({
            id: "jobs_run_policies_file_aria",
            defaultMessage: "Choose documents to add",
          }),
          chosen: (count) =>
            intl.formatMessage(
              {
                id: "jobs_run_policies_count_label",
                defaultMessage:
                  "{count, plural, =0 {None chosen} one {# document chosen} other {# documents chosen}}",
              },
              { count }
            ),
          none: intl.formatMessage({
            id: "jobs_run_policies_none_status",
            defaultMessage: "Choose at least one document to answer from.",
          }),
          empty: intl.formatMessage({
            id: "jobs_run_policies_empty",
            defaultMessage:
              "No other source is ready to answer from. Add your firm’s policies first.",
          }),
          reading: (count) =>
            intl.formatMessage(
              {
                id: "jobs_run_policies_reading_status",
                defaultMessage:
                  "{count, plural, one {# source is} other {# sources are}} still being read, and can be chosen once ready.",
              },
              { count }
            ),
        }}
      />
      <RunModelLines
        job={job}
        selection={selection}
        providerAvailable={providerAvailable}
        busy={busy}
        onChooseModel={onChooseModel}
        text={{
          missing: intl.formatMessage({
            id: "jobs_run_model_missing_body",
            defaultMessage:
              "Choose a chat model first. It answers the questions.",
          }),
          selected: (model) =>
            intl.formatMessage(
              {
                id: "jobs_run_model_label",
                defaultMessage: "Answered by {model}",
              },
              { model }
            ),
          local: intl.formatMessage({
            id: "jobs_run_model_local_body",
            defaultMessage:
              "Models that run on this computer are usually smaller, and leave more questions for a person to answer.",
          }),
          remote: intl.formatMessage({
            id: "jobs_run_remote_body",
            defaultMessage:
              "Models that don’t run on this computer receive the questions and passages from your documents.",
          }),
        }}
      />
      <StartRunButton
        error={start.error}
        busy={busy}
        disabled={!canStart}
        onStart={() => {
          if (workbookId === null) return
          start.mutate({ job, document_id: workbookId, source_ids: chosen })
        }}
      />
    </div>
  )
}
