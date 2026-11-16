import { intl } from "@/i18n/intl"
import type { PrivacyState } from "@/lib/api"

/** Why update checks cannot be switched here, or null when they can. */
export function updatesLockedText(state: PrivacyState): string | null {
  if (!state.updates.locked) return null
  if (state.updates.lockedReason === "channel")
    return intl.formatMessage(
      {
        id: "privacy_choices_updates_channel_locked_status",
        defaultMessage:
          "Updates come from {channel, select, scoop {Scoop} aur {the AUR} snap {the Snap Store} flatpak {Flatpak} nix {Nix} apt {your apt repository} other {your package manager}}, so SurfSense doesn’t check for them itself.",
      },
      { channel: state.updates.channel ?? "other" }
    )
  return intl.formatMessage({
    id: "privacy_choices_updates_policy_locked_status",
    defaultMessage:
      "Your organization’s policy turned update checks off on this computer.",
  })
}

/** Why usage statistics cannot be switched here, or null when they can. */
export function usageLockedText(state: PrivacyState): string | null {
  if (!state.usageStatistics.locked) return null
  if (state.usageStatistics.lockedReason === "do_not_track")
    return intl.formatMessage({
      id: "privacy_choices_usage_do_not_track_locked_status",
      defaultMessage:
        "Off, because DO_NOT_TRACK or SURFSENSE_NO_TELEMETRY is set on this computer.",
    })
  return intl.formatMessage({
    id: "privacy_choices_usage_policy_locked_status",
    defaultMessage:
      "Your organization’s policy turned usage statistics off on this computer.",
  })
}
