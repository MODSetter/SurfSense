import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useChatCandidates } from "@/features/models/chat-candidates/use-chat-candidates"
import { intl } from "@/i18n/intl"

import type { JobRunRead } from "../api"

import { displayModelName } from "./model-display-name"

// What a contract's review points came to, in the order a reader takes them in.
function outcomeLabels(counts: Record<string, number>) {
  return [
    intl.formatMessage(
      {
        id: "jobs_contract_changed_label",
        defaultMessage: "{count, plural, one {# changed} other {# changed}}",
      },
      { count: counts.changed ?? 0 }
    ),
    intl.formatMessage(
      {
        id: "jobs_contract_meets_label",
        defaultMessage:
          "{count, plural, one {# meets your playbook} other {# meet your playbook}}",
      },
      { count: counts.meets ?? 0 }
    ),
    intl.formatMessage(
      {
        id: "jobs_contract_not_covered_label",
        defaultMessage:
          "{count, plural, one {# not in your playbook} other {# not in your playbook}}",
      },
      { count: counts.not_covered ?? 0 }
    ),
    intl.formatMessage(
      {
        id: "jobs_contract_for_person_label",
        defaultMessage:
          "{count, plural, one {# for a person} other {# for a person}}",
      },
      { count: counts.for_person ?? 0 }
    ),
  ]
}

/** A finished contract review: what each point came to, what a person must
 *  take over, and where SurfSense's reasoning is. */
export function ContractDone({
  run,
  onOpenInStudio,
}: {
  run: JobRunRead
  onOpenInStudio: (artifactId: number) => void
}) {
  const candidates = useChatCandidates().data
  const { report, tally } = run
  const counts = report?.counts ?? {}
  const exceptions = report?.exceptions ?? []
  return (
    <div className="flex flex-col gap-3 text-sm">
      <h4 className="font-medium">
        {intl.formatMessage({
          id: "jobs_contract_done_title",
          defaultMessage: "Done",
        })}
      </h4>
      {report && tally ? (
        <p className="text-pretty">
          {intl.formatMessage(
            {
              id: "jobs_contract_done_body",
              defaultMessage:
                "SurfSense checked {points, plural, one {# review point} other {# review points}} against your playbook with {model}.",
            },
            {
              points: tally.questions,
              model: displayModelName(report.model, candidates),
            }
          )}
        </p>
      ) : null}
      {report ? (
        <ul
          aria-label={intl.formatMessage({
            id: "jobs_contract_outcomes_aria",
            defaultMessage: "Review points by outcome",
          })}
          className="flex flex-wrap gap-1.5"
        >
          {outcomeLabels(counts).map((label) => (
            <li key={label}>
              <Badge variant="secondary" className="tabular-nums">
                {label}
              </Badge>
            </li>
          ))}
        </ul>
      ) : null}
      {exceptions.length > 0 ? (
        <div className="flex flex-col gap-1">
          <p className="text-pretty">
            {intl.formatMessage(
              {
                id: "jobs_contract_for_person_body",
                defaultMessage:
                  "{count, plural, one {# review point needs} other {# review points need}} a person. Each has an internal comment in Studio that says why.",
              },
              { count: exceptions.length }
            )}
          </p>
          <ul className="list-disc ps-5 text-muted-foreground">
            {exceptions.map(([where, , point]) => (
              <li key={`${point}-${where}`}>
                {where
                  ? intl.formatMessage(
                      {
                        id: "jobs_contract_for_person_item_label",
                        defaultMessage: "{point}, at {where}",
                      },
                      { point, where }
                    )
                  : point}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {report ? (
        <p className="text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "jobs_contract_comments_body",
            defaultMessage:
              "Each change carries a comment the other side can read. SurfSense’s reasoning and the playbook quote it rests on are internal comments: they stay in Studio and are left out of every download.",
          })}
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
            id: "jobs_contract_open_button",
            defaultMessage: "Open in Studio",
          })}
        </Button>
      </div>
    </div>
  )
}
