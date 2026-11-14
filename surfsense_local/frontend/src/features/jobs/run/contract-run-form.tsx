import { useState } from "react"

import { intl } from "@/i18n/intl"

import {
  chosenPlaybook,
  contractChoices,
  contractsReading,
  defaultContract,
  playbookChoices,
  playbookReading,
} from "./contract-sources"
import { EvidenceChecklist } from "./evidence-checklist"
import { RunFileSection } from "./run-file-section"
import type { RunFormProps } from "./run-form-props"
import { RunFormHeader } from "./run-form-header"
import { RunModelLines } from "./run-model-lines"
import { StartRunButton } from "./start-run-button"
import { useSourceMarks } from "./use-source-marks"
import { useStartRun } from "./use-start-run"

/** A run's contract and the playbook it is reviewed against. */
export function ContractRunForm({
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

  const contracts = contractChoices(documents)
  // Derived, so a contract that becomes ready while the form is open is chosen.
  const contractId = contracts.some((each) => each.id === picked)
    ? picked
    : defaultContract(contracts, includedDocumentIds)
  const playbook = playbookChoices(documents, contractId)
  const chosen = chosenPlaybook(playbook, marks, includedDocumentIds)
  const usable = selection !== null && providerAvailable
  const canStart = contractId !== null && chosen.length > 0 && usable && !busy

  return (
    <div className="flex flex-col gap-6">
      <RunFormHeader title={title} busy={busy} onBack={onBack} />
      <RunFileSection
        files={contracts}
        value={contractId}
        onChange={setPicked}
        reading={contractsReading(documents)}
        accept=".docx"
        busy={busy}
        onUpload={onUploadSources}
        text={{
          label: intl.formatMessage({
            id: "jobs_run_contract_label",
            defaultMessage: "Contract to review",
          }),
          body: intl.formatMessage({
            id: "jobs_run_contract_body",
            defaultMessage:
              "The contract you received, as a Word file (.docx). Each run reviews one contract: SurfSense marks up a copy and leaves your file as it is.",
          }),
          addAnother: intl.formatMessage({
            id: "jobs_run_contract_add_another_button",
            defaultMessage: "Add a contract",
          }),
          fileAria: intl.formatMessage({
            id: "jobs_run_contract_file_aria",
            defaultMessage: "Choose a contract to add",
          }),
          empty: intl.formatMessage({
            id: "jobs_run_contract_empty",
            defaultMessage:
              "None of this workspace’s sources is a Word file (.docx). Add the contract you received. Save an older Word file (.doc) as .docx first.",
          }),
          add: intl.formatMessage({
            id: "jobs_run_contract_add_button",
            defaultMessage: "Add a contract",
          }),
          reading: (count) =>
            intl.formatMessage(
              {
                id: "jobs_run_contract_reading_status",
                defaultMessage:
                  "{count, plural, one {# Word file is} other {# Word files are}} still being read.",
              },
              { count }
            ),
        }}
      />
      <EvidenceChecklist
        choices={playbook}
        chosen={chosen}
        onMark={mark}
        reading={playbookReading(documents)}
        busy={busy}
        onUpload={onUploadSources}
        text={{
          label: intl.formatMessage({
            id: "jobs_run_playbook_label",
            defaultMessage: "Your firm’s playbook",
          }),
          body: intl.formatMessage({
            id: "jobs_run_playbook_body",
            defaultMessage:
              "Your standard positions, your own standard agreement, or both. SurfSense changes the contract only where these take a position. The sources ticked in the sidebar are chosen to start with.",
          }),
          add: intl.formatMessage({
            id: "jobs_run_playbook_add_button",
            defaultMessage: "Add playbook documents",
          }),
          fileAria: intl.formatMessage({
            id: "jobs_run_playbook_file_aria",
            defaultMessage: "Choose playbook documents to add",
          }),
          chosen: (count) =>
            intl.formatMessage(
              {
                id: "jobs_run_playbook_count_label",
                defaultMessage:
                  "{count, plural, =0 {None chosen} one {# document chosen} other {# documents chosen}}",
              },
              { count }
            ),
          none: intl.formatMessage({
            id: "jobs_run_playbook_none_status",
            defaultMessage: "Choose at least one playbook document.",
          }),
          empty: intl.formatMessage({
            id: "jobs_run_playbook_empty",
            defaultMessage:
              "No other source is ready to review against. Add your firm’s playbook first.",
          }),
          reading: (count) =>
            intl.formatMessage(
              {
                id: "jobs_run_playbook_reading_status",
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
            id: "jobs_run_contract_model_missing_body",
            defaultMessage:
              "Choose a chat model first. It reviews the contract.",
          }),
          selected: (model) =>
            intl.formatMessage(
              {
                id: "jobs_run_contract_model_label",
                defaultMessage: "Reviewed by {model}",
              },
              { model }
            ),
          local: intl.formatMessage({
            id: "jobs_run_contract_model_local_body",
            defaultMessage:
              "Models that run on this computer are usually smaller, and leave more points for a person to check.",
          }),
          remote: intl.formatMessage({
            id: "jobs_run_contract_remote_body",
            defaultMessage:
              "Models that don’t run on this computer receive the contract and passages from your playbook.",
          }),
        }}
      />
      <StartRunButton
        error={start.error}
        busy={busy}
        disabled={!canStart}
        onStart={() => {
          if (contractId === null) return
          start.mutate({ job, document_id: contractId, source_ids: chosen })
        }}
      />
    </div>
  )
}
