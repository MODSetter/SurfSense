import { memo, useCallback, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  ArrowRightIcon,
  CheckIcon,
  ChevronRightIcon,
  CircleAlertIcon,
} from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { mayBePluginStep } from "@/features/plugins/in-thread/plugin-of-step"
import { PluginStepLine } from "@/features/plugins/in-thread/plugin-step-line"
import { useOpenArtifact } from "@/features/studio/open-artifact"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { useAgentApprovals } from "./approvals-context"
import type { AgentStep, TurnSources } from "./api"
import { InlineApproval } from "./inline-approval"
import { stepLabel } from "./step-label"

function StepStatus({ status }: { status: AgentStep["status"] }) {
  if (status === "completed") {
    return <CheckIcon className="size-3.5 shrink-0 text-muted-foreground" />
  }
  if (status === "error") {
    return (
      <CircleAlertIcon
        className="size-3.5 shrink-0 text-destructive"
        aria-label={intl.formatMessage({
          id: "agent_steps_failed_aria",
          defaultMessage: "Failed",
        })}
      />
    )
  }
  return (
    <Spinner
      className="size-3.5 shrink-0"
      aria-label={intl.formatMessage({
        id: "agent_steps_running_aria",
        defaultMessage: "Running",
      })}
    />
  )
}

/** One step: what it did, and what it returned, folded until asked for. A
 *  step that made a document opens it instead of folding what it returned,
 *  which was written for the model. Memoized: a streamed token re-renders the
 *  reply, and a step keeps its object until it changes. `ask` is a request
 *  the step waits on, shown under it. */
const StepLine = memo(function StepLine({
  step,
  threadId,
  sourceTitle,
  ask,
}: {
  step: AgentStep
  threadId: number | null
  sourceTitle: (documentId: number) => string | null
  ask?: ReactNode
}) {
  const openArtifact = useOpenArtifact()
  if (threadId !== null && mayBePluginStep(step.tool)) {
    return (
      <PluginStepLine
        step={step}
        threadId={threadId}
        status={<StepStatus status={step.status} />}
        fallback={stepLabel(step, sourceTitle)}
        ask={ask}
      />
    )
  }
  const detail = step.error ?? step.output
  const line = (
    <span className="flex min-w-0 items-center gap-2">
      <StepStatus status={step.status} />
      <span className="min-w-0 truncate">{stepLabel(step, sourceTitle)}</span>
    </span>
  )
  const made = step.artifact
  if (made && openArtifact) {
    return (
      <li className="py-0.5">
        <Button
          variant="bare"
          static
          type="button"
          className="flex max-w-full items-center gap-1 rounded-sm text-left hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => openArtifact(made.id)}
        >
          {line}
          <ArrowRightIcon className="size-3.5 shrink-0" />
        </Button>
        {ask}
      </li>
    )
  }
  if (!detail || made) {
    return (
      <li className="py-0.5">
        {line}
        {ask}
      </li>
    )
  }
  return (
    <li className="py-0.5">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1 rounded-sm outline-none select-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
          {line}
          <ChevronRightIcon className="size-3.5 shrink-0 transition-transform duration-150 group-open:rotate-90 motion-reduce:transition-none" />
        </summary>
        <pre
          className={cn(
            "mt-1 ml-5.5 max-h-48 overflow-auto rounded-md bg-muted px-3 py-2 font-mono text-xs whitespace-pre-wrap",
            step.error ? "text-destructive" : "text-foreground"
          )}
        >
          {detail}
        </pre>
      </details>
      {ask}
    </li>
  )
})

/** The steps the agent took for one reply, above the answer they led to.
 *  `scope` is the turn's sources, which name a source a step used. */
export function AgentSteps({
  steps,
  scope = null,
  threadId = null,
  latest = false,
}: {
  steps: AgentStep[]
  scope?: TurnSources | null
  /** Where a plugin step reads its whole result and saves it; none while a turn is unsaved. */
  threadId?: number | null
  /** The thread's latest reply, which also asks for requests naming no step. */
  latest?: boolean
}) {
  const { approvals, answer } = useAgentApprovals()
  const sourceTitle = useCallback(
    (documentId: number) => {
      const index = scope?.document_ids.indexOf(documentId) ?? -1
      return index >= 0 ? (scope?.titles[index] ?? null) : null
    },
    [scope]
  )
  const othersWaiting = Math.max(0, approvals.length - 1)
  const askFor = (request: (typeof approvals)[number], step?: AgentStep) => (
    <InlineApproval
      request={request}
      step={step}
      othersWaiting={othersWaiting}
      onAnswer={answer}
    />
  )
  const unnamed = latest
    ? approvals.filter(
        (request) =>
          !steps.some(
            (step) => step.call_id && step.call_id === request.call_id
          )
      )
    : []
  if (steps.length === 0 && unnamed.length === 0) {
    return null
  }
  return (
    <ol
      aria-label={intl.formatMessage({
        id: "agent_steps_list_aria",
        defaultMessage: "Steps the agent took",
      })}
      className="mb-3 flex flex-col text-sm text-muted-foreground"
    >
      {steps.map((step) => {
        const request = step.call_id
          ? approvals.find((waiting) => waiting.call_id === step.call_id)
          : undefined
        return (
          <StepLine
            key={step.id}
            step={step}
            threadId={threadId}
            sourceTitle={sourceTitle}
            ask={request ? askFor(request, step) : undefined}
          />
        )
      })}
      {unnamed.map((request) => (
        <li key={request.id} className="py-0.5">
          {askFor(request)}
        </li>
      ))}
    </ol>
  )
}
