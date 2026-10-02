import { useState } from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { PermissionReply, PermissionRequest } from "./api"

/**
 * The agent's oldest waiting request, shown in full before anything runs
 * (ADR 0028). Closing the prompt is a no, and opencode then refuses every
 * other request waiting in the same chat, so the prompt says so.
 */
export function ApprovalDialog({
  request,
  othersWaiting,
  onAnswer,
}: {
  request: PermissionRequest | null
  othersWaiting: number
  onAnswer: (
    request: PermissionRequest,
    reply: PermissionReply
  ) => Promise<void>
}) {
  const [answering, setAnswering] = useState<string | null>(null)
  const busy = request !== null && answering === request.id

  const answer = async (reply: PermissionReply) => {
    if (!request || busy) return
    setAnswering(request.id)
    try {
      await onAnswer(request, reply)
    } finally {
      setAnswering(null)
    }
  }

  const shell = request?.permission === "bash"
  const command = request?.command ?? request?.patterns.join("\n") ?? ""
  return (
    <AlertDialog
      open={request !== null}
      onOpenChange={(open) => !open && void answer("reject")}
    >
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {shell
              ? intl.formatMessage({
                  id: "agent_approval_shell_title",
                  defaultMessage: "Run a shell command?",
                })
              : intl.formatMessage({
                  id: "agent_approval_other_title",
                  defaultMessage: "Allow this step?",
                })}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {shell
              ? intl.formatMessage({
                  id: "agent_approval_shell_body",
                  defaultMessage:
                    "The agent wants to run this command on your computer, with your permissions.",
                })
              : intl.formatMessage(
                  {
                    id: "agent_approval_other_body",
                    defaultMessage:
                      "The agent asks for the “{permission}” permission.",
                  },
                  { permission: request?.permission ?? "" }
                )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {command ? (
          <pre className="max-h-56 overflow-auto rounded-md bg-muted px-3 py-2 font-mono text-xs whitespace-pre-wrap text-foreground select-text">
            {command}
          </pre>
        ) : null}
        {othersWaiting > 0 ? (
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage(
              {
                id: "agent_approval_others_body",
                defaultMessage:
                  "{count, plural, one {Denying also denies # other request waiting in this chat.} other {Denying also denies # other requests waiting in this chat.}}",
              },
              { count: othersWaiting }
            )}
          </p>
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>
            {intl.formatMessage({
              id: "agent_approval_deny_button",
              defaultMessage: "Deny",
            })}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={busy}
            onClick={(event) => {
              // Answered here; closing would answer no.
              event.preventDefault()
              void answer("once")
            }}
          >
            {busy ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({
              id: "agent_approval_allow_button",
              defaultMessage: "Allow once",
            })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
