import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { isWordCopy, type Revision, type RevisionDecision } from "./api"
import { messageFrom } from "./use-studio"

function summary(revision: Revision): string | null {
  if (revision.counts) {
    return intl.formatMessage(
      {
        id: "studio_revised_copy_counts_label",
        defaultMessage:
          "{changes, plural, one {# tracked change} other {# tracked changes}}, {comments, plural, one {# comment} other {# comments}}",
      },
      {
        changes: revision.counts.changes,
        comments: revision.counts.comments,
      }
    )
  }
  if (revision.applied === null) return null
  return intl.formatMessage(
    {
      id: "studio_revised_copy_applied_label",
      defaultMessage:
        "{applied, plural, one {# change} other {# changes}} in this version",
    },
    { applied: revision.applied }
  )
}

/** Where a revised copy came from and what it holds, with Accept all and
 *  Reject all for a Word copy's tracked changes. Each decision is made as the
 *  next version; the user's own file is never changed. */
export function RevisedCopyBar({
  artifactId,
  revision,
  versionRunning,
  newest,
  onDecideAll,
}: {
  artifactId: number
  revision: Revision
  /** A version of this copy is being made; a decision waits for it. */
  versionRunning: boolean
  /** The newest ready version, which a decision starts from: an older one's
   *  counts are not what Accept all or Reject all would decide. */
  newest: boolean
  /** Rejects with the reason the next version was refused. */
  onDecideAll: (artifactId: number, decision: RevisionDecision) => Promise<void>
}) {
  const [deciding, setDeciding] = useState<RevisionDecision | null>(null)
  const [refusal, setRefusal] = useState<string | null>(null)
  const decidable =
    newest && isWordCopy(revision) && (revision.counts?.changes ?? 0) > 0
  const blocked = versionRunning || deciding !== null

  const decide = async (decision: RevisionDecision) => {
    setDeciding(decision)
    setRefusal(null)
    try {
      await onDecideAll(artifactId, decision)
    } catch (cause) {
      setRefusal(messageFrom(cause))
    } finally {
      setDeciding(null)
    }
  }

  const decisionButton = (decision: RevisionDecision, label: string) => (
    <Button
      type="button"
      size="sm"
      variant={decision === "accept_all" ? "default" : "secondary"}
      disabled={blocked}
      onClick={() => void decide(decision)}
    >
      {deciding === decision ? <Spinner data-icon="inline-start" /> : null}
      {label}
    </Button>
  )

  return (
    <div className="flex shrink-0 flex-col gap-2 border-b px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {intl.formatMessage(
              {
                id: "studio_revised_copy_title",
                defaultMessage: "Revised copy of {name}",
              },
              { name: revision.source_name }
            )}
          </p>
          <p className="text-xs text-muted-foreground">{summary(revision)}</p>
        </div>
        {decidable ? (
          <div className="flex shrink-0 items-center gap-2">
            {decisionButton(
              "accept_all",
              intl.formatMessage({
                id: "studio_revised_copy_accept_all_button",
                defaultMessage: "Accept all",
              })
            )}
            {decisionButton(
              "reject_all",
              intl.formatMessage({
                id: "studio_revised_copy_reject_all_button",
                defaultMessage: "Reject all",
              })
            )}
          </div>
        ) : null}
      </div>
      {refusal ? (
        <p role="alert" className="text-sm text-destructive">
          {refusal}
        </p>
      ) : null}
    </div>
  )
}
