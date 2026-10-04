import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import { LiveResourceUsage } from "./live-resource-usage"

export function ResourceSettings() {
  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "resources_settings_title",
        defaultMessage: "Resources",
      })}
      description={intl.formatMessage({
        id: "resources_settings_body",
        defaultMessage:
          "See how much of this computer SurfSense and other apps are using.",
      })}
    >
      <LiveResourceUsage />
    </SettingsSection>
  )
}
