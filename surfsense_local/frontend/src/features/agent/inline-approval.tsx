import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import type { AgentStep, PermissionReply, PermissionRequest } from "./api"

function inputLines(input: Record<string, unknown>) {
  return Object.entries(input)
    .map(
      ([key, value]) =>
        `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`
    )
    .join("\n")
}

/** What the step will do: the command, the call's inputs, or the paths opencode names. */
function detail(request: PermissionRequest, step: AgentStep | null) {
  if (request.command) return request.command
  if (step && Object.keys(step.input).length > 0) return inputLines(step.input)
  const patterns = request.patterns.filter((pattern) => pattern !== "*")
  return patterns.join("\n")
}

function question(request: PermissionRequest, step: AgentStep | null) {
  if (request.permission === "bash") {
    return intl.formatMessage({
      id: "agent_approval_shell_body",
      defaultMessage:
        "The agent wants to run this command on your computer, with your permissions.",
    })
  }
  if (step) {
    return intl.formatMessage({
      id: "agent_approval_step_body",
      defaultMessage: "Allow this step to run?",
    })
  }
  return intl.formatMessage(
    {
      id: "agent_approval_other_body",
      defaultMessage: "The agent asks for the “{permission}” permission.",
    },
    { permission: request.permission }
  )
}

/**
 * A request the agent waits on, asked in the reply on the step it holds back
 * (ADR 0028): Allow once or Deny, never "always". opencode refuses every other
 * request waiting in the same chat when one is denied, so the ask says so.
 */
export function InlineApproval({
  request,
  step = null,
  othersWaiting,
  onAnswer,
}: {
  request: PermissionRequest
  step?: AgentStep | null
  othersWaiting: number
  onAnswer: (
    request: PermissionRequest,
    reply: PermissionReply
  ) => Promise<void>
}) {
  const [answering, setAnswering] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // The thread may be scrolled elsewhere when the agent stops to ask.
  useEffect(() => {
    ref.current?.scrollIntoView?.({ block: "nearest" })
  }, [])

  const answer = async (reply: PermissionReply) => {
    if (answering) return
    setAnswering(true)
    try {
      await onAnswer(request, reply)
    } finally {
      setAnswering(false)
    }
  }
  const shown = detail(request, step)

  return (
    <div
      ref={ref}
      role="group"
      aria-label={intl.formatMessage({
        id: "agent_approval_group_aria",
        defaultMessage: "Approval needed",
      })}
      className="mt-1.5 ml-5.5 flex flex-col gap-2 rounded-lg border bg-card px-3 py-2.5 text-sm text-foreground"
    >
      <p>{question(request, step)}</p>
      {shown ? (
        <pre className="max-h-48 overflow-auto rounded-md bg-muted px-3 py-2 font-mono text-xs whitespace-pre-wrap select-text">
          {shown}
        </pre>
      ) : null}
      {othersWaiting > 0 ? (
        <p className="text-xs text-muted-foreground">
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
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={answering}
          onClick={() => void answer("reject")}
        >
          {intl.formatMessage({
            id: "agent_approval_deny_button",
            defaultMessage: "Deny",
          })}
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={answering}
          onClick={() => void answer("once")}
        >
          {answering ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "agent_approval_allow_button",
            defaultMessage: "Allow once",
          })}
        </Button>
      </div>
    </div>
  )
}
