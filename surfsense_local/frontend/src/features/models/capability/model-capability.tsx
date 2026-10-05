import { useId } from "react"

import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { intl } from "@/i18n/intl"

import { useSelection } from "../selection/use-selection"
import type { ModelCapability } from "./api"
import { capabilityLabel } from "./capability-label"
import { useAgentTrial } from "./use-agent-trial"

/**
 * What the chat model in use is measured to do, under the model in use: the
 * level, its evidence, and for a model nobody measured, the agent trial.
 */
export function ModelCapabilitySummary() {
  const selection = useSelection("text_gen")
  const capability = selection.data?.capability
  if (!capability) return null

  return (
    <section
      aria-label={intl.formatMessage({
        id: "models_capability_summary_aria",
        defaultMessage: "What this chat model can do",
      })}
      className="flex flex-col gap-1.5 rounded-lg border px-3 py-2.5 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant={
            capability.level === "studio_only" ||
            capability.level === "not_measured"
              ? "outline"
              : "secondary"
          }
        >
          {capabilityLabel(capability.level)}
        </Badge>
        <span className="text-muted-foreground">
          {intl.formatMessage(
            {
              id: "models_capability_level_body",
              defaultMessage:
                "{level, select, agent {New chats work on your files with the agent.} agent_limited {New chats use the agent, which may need a nudge, such as asking it to check each page.} studio_only {Chats answer questions, and Studio writes Word and PDF from Markdown.} other {Chats answer questions, and Studio works as before.}}",
            },
            { level: capability.level }
          )}
        </span>
      </div>
      <Evidence capability={capability} />
      {capability.note ? (
        <p className="text-muted-foreground">{capability.note}</p>
      ) : null}
      {capability.level === "not_measured" ? (
        <AgentTrialControl capability={capability} />
      ) : null}
    </section>
  )
}

function Evidence({ capability }: { capability: ModelCapability }) {
  const measured = capability.measured
  if (measured) {
    return (
      <p className="text-muted-foreground">
        {intl.formatMessage(
          {
            id: "models_capability_evidence_body",
            defaultMessage:
              "Passed {passed, number} of {counted, number} cases in SurfSense’s tests on {date, date, ::yyyyMMMd}.",
          },
          {
            passed: measured.passed,
            counted: measured.counted,
            // Noon UTC, so the day reads the same in every time zone.
            date: new Date(`${measured.measured_on}T12:00:00Z`),
          }
        )}
        {measured.provisional
          ? ` ${intl.formatMessage({
              id: "models_capability_provisional_body",
              defaultMessage: "Provisional: one run per case so far.",
            })}`
          : null}
      </p>
    )
  }
  return (
    <p className="text-muted-foreground">
      {intl.formatMessage(
        {
          id: "models_capability_not_measured_body",
          defaultMessage:
            "{code, select, measured_elsewhere {SurfSense measured this model through {host}, not on a computer of your own.} alias {A name ending in “latest” can point to a new model, so it is never counted as measured.} other {SurfSense has not measured this model.}}",
        },
        {
          code: capability.reason.code,
          host: String(capability.reason.values.host ?? ""),
        }
      )}
    </p>
  )
}

function AgentTrialControl({ capability }: { capability: ModelCapability }) {
  const trial = useAgentTrial()
  const warningId = useId()
  const { offered, enabled, blocked } = capability.agent_trial

  if (!offered) {
    return blocked ? (
      <p className="text-muted-foreground">
        {intl.formatMessage(
          {
            id: "models_capability_trial_blocked_body",
            defaultMessage:
              "{blocked, select, window_below_floor {The agent needs a window of at least 32,768 tokens, and this model has less.} other {The model catalog does not say this model can call tools, so the agent cannot be tried with it.}}",
          },
          { blocked }
        )}
      </p>
    ) : null
  }

  return (
    <div className="flex flex-col gap-1 pt-1">
      <label className="flex w-fit cursor-pointer items-center gap-2 font-medium">
        <Switch
          checked={trial.isPending ? !enabled : enabled}
          disabled={trial.isPending}
          aria-describedby={warningId}
          onCheckedChange={(checked) => trial.mutate(checked)}
        />
        {intl.formatMessage({
          id: "models_capability_trial_label",
          defaultMessage: "Try the agent",
        })}
      </label>
      <p id={warningId} className="text-muted-foreground">
        {intl.formatMessage({
          id: "models_capability_trial_warning_body",
          defaultMessage:
            "SurfSense has not tested the agent with this model, so it may stop early or make mistakes in new chats.",
        })}
      </p>
      {trial.isError ? (
        <p role="alert" className="text-destructive">
          {intl.formatMessage({
            id: "models_capability_trial_error",
            defaultMessage: "Could not change this setting. Try again.",
          })}
        </p>
      ) : null}
    </div>
  )
}
