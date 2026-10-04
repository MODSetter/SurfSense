import {
  ArrowRightIcon,
  CheckIcon,
  ChevronRightIcon,
  CircleAlertIcon,
} from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { useOpenArtifact } from "@/features/studio/open-artifact"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { AgentStep } from "./api"
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
 *  which was written for the model. */
function StepLine({ step }: { step: AgentStep }) {
  const openArtifact = useOpenArtifact()
  const detail = step.error ?? step.output
  const line = (
    <span className="flex min-w-0 items-center gap-2">
      <StepStatus status={step.status} />
      <span className="min-w-0 truncate">{stepLabel(step)}</span>
    </span>
  )
  const made = step.artifact
  if (made && openArtifact) {
    return (
      <li className="py-0.5">
        <button
          type="button"
          className="flex max-w-full cursor-pointer items-center gap-1 rounded-sm text-left outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => openArtifact(made.id)}
        >
          {line}
          <ArrowRightIcon className="size-3.5 shrink-0" />
        </button>
      </li>
    )
  }
  if (!detail || made) {
    return <li className="py-0.5">{line}</li>
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
    </li>
  )
}

/** The steps the agent took for one reply, above the answer they led to. */
export function AgentSteps({ steps }: { steps: AgentStep[] }) {
  if (steps.length === 0) {
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
      {steps.map((step) => (
        <StepLine key={step.id} step={step} />
      ))}
    </ol>
  )
}
