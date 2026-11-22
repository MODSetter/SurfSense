import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { RelativeTime } from "@/components/relative-time"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { useChatCandidates } from "@/features/models/chat-candidates/use-chat-candidates"
import type { DocumentStatus } from "@/features/sources/api"
import { cancelArtifact, regenerateArtifact } from "@/features/studio/api"
import { studioKeys } from "@/features/studio/query-keys"
import { intl } from "@/i18n/intl"

import { AllJobsButton } from "../all-jobs-button"
import type { JobRunRead } from "../api"
import { jobRunnerOfKey, jobTitleOfKey } from "../catalog"
import { ConfirmSuggestionsButton } from "../confirm/confirm-suggestions-button"
import { jobsErrorText } from "../job-error-text"
import { jobsKeys } from "../query-keys"
import { WORD_CLAUSES } from "../runners"
import { useJobPacks } from "../use-job-packs"

import { ContractDone } from "./contract-done"
import { displayModelName } from "./model-display-name"
import { isRunning, runStage, type RunStage } from "./run-stage"
import { useJobRun } from "./use-job-run"

// The pack's own counts of rows it left alone, not answer words.
const NOT_ANSWER_WORDS = new Set(["blank", "skipped"])

// A contract review counts review points where a questionnaire counts questions.
function contractStageText(stage: RunStage): string | null {
  switch (stage.name) {
    case "reading_file":
      return intl.formatMessage({
        id: "jobs_progress_reading_contract_status",
        defaultMessage: "Reading the contract…",
      })
    case "reading":
      return intl.formatMessage(
        {
          id: "jobs_progress_reading_playbook_status",
          defaultMessage:
            "Reading your playbook, then {total, plural, one {# review point} other {# review points}}…",
        },
        { total: stage.total }
      )
    case "answering":
      return intl.formatMessage(
        {
          id: "jobs_progress_points_status",
          defaultMessage: "{done, number} of {total, number} review points",
        },
        { done: stage.done, total: stage.total }
      )
    case "writing":
      return intl.formatMessage({
        id: "jobs_progress_marking_up_status",
        defaultMessage: "Marking up a copy of your contract…",
      })
    default:
      return stageText(stage)
  }
}

function stageText(stage: RunStage): string | null {
  switch (stage.name) {
    case "waiting":
      return intl.formatMessage({
        id: "jobs_progress_waiting_status",
        defaultMessage: "Waiting to start…",
      })
    case "reading_file":
      return intl.formatMessage({
        id: "jobs_progress_reading_workbook_status",
        defaultMessage: "Reading the workbook…",
      })
    case "reading":
      return intl.formatMessage(
        {
          id: "jobs_progress_reading_status",
          defaultMessage:
            "Reading your documents, then {total, plural, one {# question} other {# questions}}…",
        },
        { total: stage.total }
      )
    case "answering":
      return intl.formatMessage(
        {
          id: "jobs_progress_questions_status",
          defaultMessage: "{done, number} of {total, number} questions",
        },
        { done: stage.done, total: stage.total }
      )
    case "writing":
      return intl.formatMessage({
        id: "jobs_progress_writing_status",
        defaultMessage: "Writing the answers into a copy of your workbook…",
      })
    default:
      return null
  }
}

// How a run that ended reads, as its view's title.
function endedTitle(status: "ready" | "failed" | "cancelled"): string {
  switch (status) {
    case "ready":
      return intl.formatMessage({
        id: "jobs_progress_done_title",
        defaultMessage: "Done",
      })
    case "failed":
      return intl.formatMessage({
        id: "jobs_progress_failed_title",
        defaultMessage: "The run stopped",
      })
    case "cancelled":
      return intl.formatMessage({
        id: "jobs_progress_cancelled_title",
        defaultMessage: "Cancelled",
      })
  }
}

/**
 * Says once that a run seen going has ended, as its title reads. Going's own
 * status line covers the run until then, and leaves with it; a run opened
 * after it ended is not news.
 */
function RunEndAnnouncer({ status }: { status: DocumentStatus | undefined }) {
  const [sawRunning, setSawRunning] = useState(false)
  if (!sawRunning && status !== undefined && isRunning(status))
    setSawRunning(true)

  // Mounted empty and filled only later, so the region exists before it speaks.
  return (
    <span role="status" className="sr-only">
      {sawRunning && status !== undefined && !isRunning(status)
        ? endedTitle(status)
        : ""}
    </span>
  )
}

// Null is indeterminate: nothing is counted until the first answer.
function progressValue(stage: RunStage): number | null {
  if (stage.name === "answering")
    return Math.round((stage.done / stage.total) * 100)
  return stage.name === "writing" ? 100 : null
}

function useRunAction(
  workspaceId: number,
  act: (artifactId: number) => Promise<unknown>
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: act,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: studioKeys.artifacts(workspaceId),
      })
      void queryClient.invalidateQueries({
        queryKey: jobsKeys.runs(workspaceId),
      })
    },
  })
}

type RunAction = ReturnType<typeof useRunAction>

function Going({
  run,
  stage,
  contract,
  cancel,
}: {
  run: JobRunRead
  stage: RunStage
  contract: boolean
  cancel: RunAction
}) {
  return (
    <div className="flex flex-col gap-3">
      <p role="status" className="text-sm tabular-nums">
        {contract ? contractStageText(stage) : stageText(stage)}
      </p>
      <Progress
        value={progressValue(stage)}
        aria-label={
          contract
            ? intl.formatMessage({
                id: "jobs_progress_points_aria",
                defaultMessage: "Review points checked",
              })
            : intl.formatMessage({
                id: "jobs_progress_aria",
                defaultMessage: "Questions answered",
              })
        }
      />
      <p className="text-sm text-pretty text-muted-foreground">
        {intl.formatMessage({
          id: "jobs_progress_close_body",
          defaultMessage:
            "You can close Jobs and keep working. Keep SurfSense open until the run is done: quitting stops it.",
        })}
      </p>
      <Button
        type="button"
        variant="outline"
        className="self-start"
        disabled={cancel.isPending}
        onClick={() => cancel.mutate(run.artifact_id)}
      >
        {cancel.isPending ? <Spinner data-icon="inline-start" /> : null}
        {intl.formatMessage({
          id: "jobs_progress_cancel_button",
          defaultMessage: "Cancel run",
        })}
      </Button>
      {cancel.error ? (
        <p role="alert" className="text-sm text-destructive">
          {jobsErrorText(cancel.error)}
        </p>
      ) : null}
    </div>
  )
}

function Done({
  run,
  workspaceId,
  onOpenInStudio,
}: {
  run: JobRunRead
  workspaceId: number
  onOpenInStudio: (artifactId: number) => void
}) {
  const candidates = useChatCandidates().data
  const { report, tally } = run
  const words = Object.entries(report?.counts ?? {})
    .filter(([word, count]) => !NOT_ANSWER_WORDS.has(word) && count > 0)
    .toSorted(([, a], [, b]) => b - a)
  return (
    <div className="flex flex-col gap-3 text-sm">
      <h4 className="font-medium">{endedTitle("ready")}</h4>
      {report && tally ? (
        <p className="text-pretty">
          {intl.formatMessage(
            {
              id: "jobs_progress_done_body",
              defaultMessage:
                "SurfSense answered {answered, plural, one {# question} other {# questions}} of {questions, number} with {model}.",
            },
            {
              answered: tally.answered,
              questions: tally.questions,
              model: displayModelName(report.model, candidates),
            }
          )}
        </p>
      ) : null}
      {report?.checker ? (
        <p className="text-pretty">
          {intl.formatMessage(
            {
              id: "jobs_progress_checker_body",
              defaultMessage: "Each answer was checked again by {checker}.",
            },
            { checker: displayModelName(report.checker, candidates) }
          )}
        </p>
      ) : null}
      {words.length > 0 ? (
        <ul
          aria-label={intl.formatMessage({
            id: "jobs_progress_answers_aria",
            defaultMessage: "Answers by kind",
          })}
          className="flex flex-wrap gap-1.5"
        >
          {words.map(([word, count]) => (
            <li key={word}>
              <Badge variant="secondary" className="tabular-nums">
                {word} {intl.formatNumber(count)}
              </Badge>
            </li>
          ))}
        </ul>
      ) : null}
      {report && tally && tally.for_person > 0 ? (
        <p className="text-pretty">
          {intl.formatMessage(
            {
              id: "jobs_progress_for_person_body",
              defaultMessage:
                "{count, plural, one {# question needs} other {# questions need}} a person: see the sheet “{sheet}”.",
            },
            { count: tally.for_person, sheet: report.sheets?.exceptions ?? "" }
          )}
        </p>
      ) : null}
      {run.open_suggestion_count > 0 ? (
        <p className="text-pretty">
          {intl.formatMessage(
            {
              id: "jobs_progress_suggestions_body",
              defaultMessage:
                "{count, plural, one {# suggested answer is} other {# suggested answers are}} waiting for you to check and confirm.",
            },
            { count: run.open_suggestion_count }
          )}
        </p>
      ) : null}
      {tally && tally.skipped > 0 ? (
        <p className="text-pretty text-muted-foreground">
          {intl.formatMessage(
            {
              id: "jobs_progress_skipped_body",
              defaultMessage:
                "{count, plural, one {# row was} other {# rows were}} left as they were: hidden, locked or already answered.",
            },
            { count: tally.skipped }
          )}
        </p>
      ) : null}
      {report ? (
        <p className="text-pretty text-muted-foreground">
          {intl.formatMessage(
            {
              id: "jobs_progress_send_body",
              defaultMessage:
                "Before you send the copy, check the sheets “{answers}” and “{exceptions}”, and delete them if the recipient shouldn’t see them.",
            },
            {
              answers: report.sheets?.answers ?? "",
              exceptions: report.sheets?.exceptions ?? "",
            }
          )}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          onClick={() =>
            onOpenInStudio(run.newest_ready_version_id ?? run.artifact_id)
          }
        >
          {intl.formatMessage({
            id: "jobs_progress_open_button",
            defaultMessage: "Open in Studio",
          })}
        </Button>
        {run.open_suggestions.length > 0 ? (
          <ConfirmSuggestionsButton
            workspaceId={workspaceId}
            rootId={run.artifact_id}
            suggestions={run.open_suggestions}
            disabled={run.running}
          />
        ) : null}
      </div>
    </div>
  )
}

function stoppedText(failed: boolean, contract: boolean): string {
  if (contract)
    return failed
      ? intl.formatMessage({
          id: "jobs_progress_contract_failed_body",
          defaultMessage: "It didn’t finish, so nothing was changed.",
        })
      : intl.formatMessage({
          id: "jobs_progress_contract_cancelled_body",
          defaultMessage:
            "Nothing was changed. Running it again starts from the first review point.",
        })
  return failed
    ? intl.formatMessage({
        id: "jobs_progress_failed_body",
        defaultMessage: "It didn’t finish, so no answers were written.",
      })
    : intl.formatMessage({
        id: "jobs_progress_cancelled_body",
        defaultMessage:
          "Nothing was written. Running it again starts from the first question.",
      })
}

function Stopped({
  run,
  again,
  jobName,
  contract,
  onChooseFile,
}: {
  run: JobRunRead
  again: RunAction
  jobName: string
  contract: boolean
  onChooseFile: (job: string, title: string) => void
}) {
  const failed = run.status === "failed"
  return (
    <div className="flex flex-col gap-3 text-sm">
      <h4 className="font-medium">
        {endedTitle(failed ? "failed" : "cancelled")}
      </h4>
      <p className="text-pretty">{stoppedText(failed, contract)}</p>
      {failed && run.error ? (
        <p className="line-clamp-4 whitespace-pre-wrap text-muted-foreground">
          {run.error}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          disabled={again.isPending}
          onClick={() => again.mutate(run.artifact_id)}
        >
          {again.isPending ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "jobs_progress_retry_button",
            defaultMessage: "Run again",
          })}
        </Button>
        {failed ? (
          <Button
            type="button"
            variant="outline"
            disabled={again.isPending}
            onClick={() => onChooseFile(run.job, jobName)}
          >
            {contract
              ? intl.formatMessage({
                  id: "jobs_progress_choose_contract_button",
                  defaultMessage: "Choose another contract",
                })
              : intl.formatMessage({
                  id: "jobs_progress_choose_workbook_button",
                  defaultMessage: "Choose another workbook",
                })}
          </Button>
        ) : null}
      </div>
      {again.error ? (
        <p role="alert" className="text-destructive">
          {jobsErrorText(again.error)}
        </p>
      ) : null}
    </div>
  )
}

/** One run, re-read while it goes on: how far it has got, then what it wrote. */
export function JobRunProgress({
  workspaceId,
  runId,
  onOpenInStudio,
  onChooseFile,
  onBack,
}: {
  workspaceId: number
  runId: number
  onOpenInStudio: (artifactId: number) => void
  onChooseFile: (job: string, title: string) => void
  onBack: () => void
}) {
  const read = useJobRun(workspaceId, runId, { poll: true })
  const packs = useJobPacks().data
  const cancel = useRunAction(workspaceId, (id) => cancelArtifact(id))
  const again = useRunAction(workspaceId, (id) => regenerateArtifact(id))
  const run = read.data

  let body
  if (read.isPending) {
    body = (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
    )
  } else if (read.error) {
    body = (
      <p role="alert" className="text-sm text-destructive">
        {intl.formatMessage({
          id: "jobs_progress_load_error",
          defaultMessage: "Could not load this run.",
        })}
      </p>
    )
  } else if (!run) {
    body = (
      <p className="text-sm text-muted-foreground">
        {intl.formatMessage({
          id: "jobs_progress_gone_body",
          defaultMessage: "This run was deleted.",
        })}
      </p>
    )
  } else {
    const jobName = jobTitleOfKey(run.job, packs)
    const contract =
      (run.report?.runner ?? jobRunnerOfKey(run.job, packs)) === WORD_CLAUSES
    const stage = runStage(run.status, run.progress)
    body = (
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-0.5">
          <h3 className="text-base font-medium text-balance">{run.title}</h3>
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage(
              {
                id: "jobs_progress_started_label",
                defaultMessage: "{job}, started {time}",
              },
              {
                job: jobName,
                time: (
                  <RelativeTime
                    date={new Date(run.created_at)}
                    className="h-auto text-sm"
                  />
                ),
              }
            )}
          </p>
        </div>
        {isRunning(run.status) ? (
          <Going run={run} stage={stage} contract={contract} cancel={cancel} />
        ) : run.status === "ready" && contract ? (
          <ContractDone run={run} onOpenInStudio={onOpenInStudio} />
        ) : run.status === "ready" ? (
          <Done
            run={run}
            workspaceId={workspaceId}
            onOpenInStudio={onOpenInStudio}
          />
        ) : (
          <Stopped
            run={run}
            again={again}
            jobName={jobName}
            contract={contract}
            onChooseFile={onChooseFile}
          />
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <AllJobsButton
        onClick={onBack}
        disabled={cancel.isPending || again.isPending}
      />
      {body}
      <RunEndAnnouncer status={run?.status} />
    </div>
  )
}
