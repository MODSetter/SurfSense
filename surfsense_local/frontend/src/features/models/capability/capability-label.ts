import { intl } from "@/i18n/intl"

import type { CapabilityLevel } from "./api"

/** The short label a model row and the settings show for a level: how it did in the Agentic tests. */
export function capabilityLabel(level: CapabilityLevel) {
  return intl.formatMessage(
    {
      id: "models_capability_level_label",
      defaultMessage:
        "{level, select, agent {Agentic} agent_limited {Agentic, may need nudges} studio_only {Low Agentic score} other {Not tested}}",
    },
    { level }
  )
}
