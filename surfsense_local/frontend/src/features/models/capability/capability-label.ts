import { intl } from "@/i18n/intl"

import type { CapabilityLevel } from "./api"

/** The short label a model row and the settings show for a level. */
export function capabilityLabel(level: CapabilityLevel) {
  return intl.formatMessage(
    {
      id: "models_capability_level_label",
      defaultMessage:
        "{level, select, agent {Agent} agent_limited {Agent, may need nudges} studio_only {Studio only} other {Not measured}}",
    },
    { level }
  )
}
