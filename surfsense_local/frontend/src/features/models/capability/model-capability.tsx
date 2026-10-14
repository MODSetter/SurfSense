import { Badge } from "@/components/ui/badge"
import { intl } from "@/i18n/intl"

import { useSelection } from "../selection/use-selection"
import type { ModelCapability } from "./api"
import { capabilityLabel } from "./capability-label"

/**
 * What the chat model in use is measured to do, under the model in use: the
 * level, its evidence, and the mode its new chats start in.
 */
export function ModelCapabilitySummary() {
  const selection = useSelection("text_gen")
  const capability = selection.data?.capability
  if (!capability) return null
  // Listed at the agent level without a run: said once, never as a pass.
  const assumed = capability.measured?.assumed === true

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
          {assumed
            ? intl.formatMessage({
                id: "models_capability_assumed_body",
                defaultMessage:
                  "Not run: SurfSense expects this expensive flagship model to pass.",
              })
            : intl.formatMessage(
                {
                  id: "models_capability_level_body",
                  defaultMessage:
                    "{level, select, agent {Passed SurfSense’s Agentic tests.} agent_limited {Near the bar in SurfSense’s Agentic tests: it may need a nudge, such as asking it to check each page.} studio_only {Below the bar in SurfSense’s Agentic tests, so Studio writes Word and PDF from Markdown.} other {Not tested for Agentic mode yet.}}",
                },
                { level: capability.level }
              )}
        </span>
      </div>
      {assumed ? null : <Evidence capability={capability} />}
      {capability.note && !assumed ? (
        <p className="text-muted-foreground">{capability.note}</p>
      ) : null}
      <Modes capability={capability} />
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

function Modes({ capability }: { capability: ModelCapability }) {
  const { modes } = capability
  return (
    <div className="flex flex-col gap-1 pt-1">
      <p>
        {intl.formatMessage(
          {
            id: "models_capability_default_mode_body",
            defaultMessage:
              "{mode, select, agentic {New chats start in Agentic mode.} other {New chats start in Basic (Q&A) mode.}}",
          },
          { mode: modes.default_mode }
        )}
      </p>
      <p className="text-muted-foreground">
        {modes.agentic_allowed
          ? intl.formatMessage({
              id: "models_capability_modes_body",
              defaultMessage:
                "Choose Basic (Q&A) or Agentic for each new chat in the composer. A chat keeps the mode it started in.",
            })
          : intl.formatMessage(
              {
                id: "models_capability_agentic_blocked_body",
                defaultMessage:
                  "{blocked, select, agent_not_installed {Agentic mode isn’t available: this install doesn’t include the agent.} window_below_floor {Agentic mode isn’t available: it needs a context window of at least 32,768 tokens, and this model has less.} other {Agentic mode isn’t available: this model can’t use tools.}}",
              },
              { blocked: modes.blocked ?? "" }
            )}
      </p>
    </div>
  )
}
