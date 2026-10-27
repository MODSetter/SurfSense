import { intl } from "@/i18n/intl"

import type { ModelCapability } from "./api"

// The API's floor for Agentic (capability/agent_gate.py WINDOW_FLOOR), shown, never enforced here.
const AGENTIC_WINDOW_FLOOR = 32_768

/** What chat offers on this model: both modes and how well, or Basic and why. */
export function chatLine({ level, modes }: ModelCapability): string {
  if (!modes.agentic_allowed) {
    return intl.formatMessage(
      {
        id: "models_capability_chat_blocked_body",
        defaultMessage:
          "{blocked, select, window_below_floor {Basic only. Agentic needs a context window of at least {tokens, number} tokens.} agent_not_installed {Basic only. This install doesn’t include the agent.} other {Basic only. Agentic needs a model that can use tools.}}",
      },
      { blocked: modes.blocked ?? "", tokens: AGENTIC_WINDOW_FLOOR }
    )
  }
  return intl.formatMessage(
    {
      id: "models_capability_chat_body",
      defaultMessage:
        "{level, select, agent {Basic and Agentic. Choose the mode in the composer.} agent_limited {Basic and Agentic. In Agentic it may need a nudge, such as asking it to check its work.} studio_only {Basic and Agentic. Agentic may not finish longer tasks well.} other {Basic and Agentic. Agentic isn’t tested with this model yet.}}",
    },
    { level }
  )
}

/** What Studio makes with it: the same rule Studio applies (`studio`). */
export function studioLine({ studio }: ModelCapability): string {
  return intl.formatMessage(
    {
      id: "models_capability_studio_body",
      defaultMessage:
        "{studio, select, full {Full designed pages, and Word, Excel and slide files.} other {Simple pages and documents. A stronger model writes full designed pages and Word, Excel and slide files.}}",
    },
    { studio }
  )
}

/** Where the rating came from, last and small: evidence, not a headline. */
export function testedLine({ measured, reason }: ModelCapability): string {
  if (measured?.assumed) {
    return intl.formatMessage({
      id: "models_capability_tested_assumed_body",
      defaultMessage: "Not tested. Expected to pass, as a flagship model.",
    })
  }
  if (measured) {
    return intl.formatMessage(
      {
        id: "models_capability_tested_body",
        defaultMessage:
          "{short, select, yes {From a short test: {passed, number} of {counted, number} cases passed, {date, date, ::yyyyMMMd}.} other {Tested: {passed, number} of {counted, number} cases passed, {date, date, ::yyyyMMMd}.}}",
      },
      {
        short: measured.provisional ? "yes" : "no",
        passed: measured.passed,
        counted: measured.counted,
        // Noon UTC, so the day reads the same in every time zone.
        date: new Date(`${measured.measured_on}T12:00:00Z`),
      }
    )
  }
  return intl.formatMessage(
    {
      id: "models_capability_untested_body",
      defaultMessage:
        "{code, select, measured_elsewhere {Tested through {host}, not on your own computer or server.} alias {Not tested. A name ending in “latest” can point to a new model.} other {Not tested yet.}}",
    },
    { code: reason.code, host: String(reason.values.host ?? "") }
  )
}
