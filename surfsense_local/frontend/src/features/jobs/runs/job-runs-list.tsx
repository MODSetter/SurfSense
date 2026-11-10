import { RelativeTime } from "@/components/relative-time"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { GuideLink } from "@/features/guides/guide-link"
import { intl } from "@/i18n/intl"

import type { JobRunSummary, PackInfo } from "../api"
import { jobRunnerOfKey, jobTitleOfKey } from "../catalog"
import { WORD_CLAUSES } from "../runners"
import { runStage } from "../run/run-stage"

import { RUNS_SHOWN, useJobRuns } from "./use-job-runs"

// A contract review counts review points where a questionnaire counts questions.
function contractStatusLine(run: JobRunSummary): string {
  const stage = runStage(run.status, run.progress)
  switch (stage.name) {
    case "answering":
      return intl.formatMessage(
        {
          id: "jobs_runs_points_status",
          defaultMessage: "{done, number} of {total, number} review points",
        },
        { done: stage.done, total: stage.total }
      )
    case "writing":
      return intl.formatMessage({
        id: "jobs_runs_marking_up_status",
        defaultMessage: "Marking up the contract",
      })
    case "ready":
      if (run.tally)
        return intl.formatMessage(
          {
            id: "jobs_runs_done_points_status",
            defaultMessage:
              "Done, {count, plural, one {# review point} other {# review points}}",
          },
          { count: run.tally.questions }
        )
      return statusLine(run)
    default:
      return statusLine(run)
  }
}

function statusLine(run: JobRunSummary): string {
  const stage = runStage(run.status, run.progress)
  switch (stage.name) {
    case "waiting":
      return intl.formatMessage({
        id: "jobs_runs_waiting_status",
        defaultMessage: "Waiting to start",
      })
    case "reading_file":
    case "reading":
      return intl.formatMessage({
        id: "jobs_runs_reading_status",
        defaultMessage: "Reading your documents",
      })
    case "answering":
      return intl.formatMessage(
        {
          id: "jobs_runs_progress_status",
          defaultMessage: "{done, number} of {total, number} questions",
        },
        { done: stage.done, total: stage.total }
      )
    case "writing":
      return intl.formatMessage({
        id: "jobs_runs_writing_status",
        defaultMessage: "Writing the answers",
      })
    case "ready":
      return run.tally
        ? intl.formatMessage(
            {
              id: "jobs_runs_done_status",
              defaultMessage:
                "Done, {count, plural, one {# question} other {# questions}}",
            },
            { count: run.tally.questions }
          )
        : intl.formatMessage({
            id: "jobs_runs_done_plain_status",
            defaultMessage: "Done",
          })
    case "failed":
      return intl.formatMessage({
        id: "jobs_runs_failed_status",
        defaultMessage: "Stopped",
      })
    case "cancelled":
      return intl.formatMessage({
        id: "jobs_runs_cancelled_status",
        defaultMessage: "Cancelled",
      })
  }
}

/** The workspace's latest runs, newest first; older ones are in Studio. */
export function JobRunsList({
  workspaceId,
  packs,
  offered,
  onOpenRun,
}: {
  workspaceId: number
  packs: readonly PackInfo[] | undefined
  // Some job here can run, so an empty list is worth saying so.
  offered: boolean
  onOpenRun: (runId: number) => void
}) {
  const runs = useJobRuns(workspaceId)
  const listed = runs.data ?? []
  if (!offered && listed.length === 0 && !runs.error) return null

  const title = (
    <h3 className="text-sm font-medium">
      {intl.formatMessage({
        id: "jobs_runs_title",
        defaultMessage: "Recent runs",
      })}
    </h3>
  )
  let body
  if (runs.isPending) {
    body = <Skeleton className="h-14 w-full" />
  } else if (runs.error) {
    body = (
      <p role="alert" className="text-sm text-destructive">
        {intl.formatMessage({
          id: "jobs_runs_error",
          defaultMessage: "Could not load recent runs.",
        })}
      </p>
    )
  } else if (listed.length === 0) {
    body = (
      <div className="flex flex-col gap-1.5">
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "jobs_runs_empty",
            defaultMessage:
              "No runs yet. Each run shows here, and its copy in Studio.",
          })}
        </p>
        <GuideLink guide="security-questionnaire" surface="jobs_runs_empty">
          {intl.formatMessage({
            id: "jobs_runs_guide_link",
            defaultMessage: "How to fill in a security questionnaire",
          })}
        </GuideLink>
      </div>
    )
  } else {
    body = (
      <>
        <ul className="flex flex-col gap-1">
          {listed.slice(0, RUNS_SHOWN).map((run) => (
            <li key={run.artifact_id}>
              <Button
                type="button"
                variant="ghost"
                static
                className="h-auto w-full justify-between gap-4 px-2.5 py-2 text-left font-normal"
                onClick={() => onOpenRun(run.artifact_id)}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">{run.title}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {intl.formatMessage(
                      {
                        id: "jobs_runs_started_label",
                        defaultMessage: "{job}, {time}",
                      },
                      {
                        job: jobTitleOfKey(run.job, packs),
                        time: (
                          <RelativeTime
                            date={new Date(run.created_at)}
                            showTooltip={false}
                            className="h-auto"
                          />
                        ),
                      }
                    )}
                  </span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {jobRunnerOfKey(run.job, packs) === WORD_CLAUSES
                      ? contractStatusLine(run)
                      : statusLine(run)}
                  </span>
                  {run.open_suggestion_count > 0 ? (
                    <Badge variant="secondary">
                      {intl.formatMessage(
                        {
                          id: "jobs_runs_suggestions_label",
                          defaultMessage:
                            "{count, plural, one {# suggestion to confirm} other {# suggestions to confirm}}",
                        },
                        { count: run.open_suggestion_count }
                      )}
                    </Badge>
                  ) : null}
                </span>
              </Button>
            </li>
          ))}
        </ul>
        {listed.length > RUNS_SHOWN ? (
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage({
              id: "jobs_runs_older_body",
              defaultMessage: "Older runs are in Studio.",
            })}
          </p>
        ) : null}
      </>
    )
  }
  return (
    <section className="flex flex-col gap-2">
      {title}
      {body}
    </section>
  )
}
