import { intl } from "@/i18n/intl"
import type { PrivacyState } from "@/lib/api"

/**
 * What onboarding and Settings say about each choice: a one-line summary, and
 * the full description, with every host it reaches, behind the info icon.
 */
export type ChoiceText = { summary: string; details: string; label: string }

export function updatesText(state: PrivacyState): ChoiceText {
  const { host, fallbackHost } = state.updates
  const label = intl.formatMessage({
    id: "privacy_choices_updates_details_aria",
    defaultMessage: "What an update check sends",
  })
  if (!fallbackHost)
    return {
      label,
      summary: intl.formatMessage({
        id: "privacy_choices_updates_mirror_summary_body",
        defaultMessage:
          "Checks your organization’s update server once a day. No ID sent.",
      }),
      details: intl.formatMessage(
        {
          id: "privacy_choices_updates_mirror_details_body",
          defaultMessage:
            "Once a day, SurfSense asks {host}, your organization’s update server, for a newer version, sending your IP address, the app’s version and your system, but no ID. Updates download from {host}, or a server it names, and install when you quit.",
        },
        { host }
      ),
    }
  return {
    label,
    summary: intl.formatMessage({
      id: "privacy_choices_updates_summary_body",
      defaultMessage: "Checks for a newer version once a day. No ID sent.",
    }),
    details: intl.formatMessage(
      {
        id: "privacy_choices_updates_details_body",
        defaultMessage:
          "Once a day, SurfSense asks {host} for a newer version, sending your IP address, the app’s version and your system, but no ID. If that fails, github.com sees only your IP address and operating system. Updates download from github.com and githubusercontent.com and install when you quit.",
      },
      { host }
    ),
  }
}

export function usageText(state: PrivacyState): ChoiceText {
  const { host } = state.usageStatistics
  return {
    label: intl.formatMessage({
      id: "privacy_choices_usage_details_aria",
      defaultMessage: "What usage statistics send",
    }),
    summary: intl.formatMessage({
      id: "privacy_choices_usage_summary_body",
      defaultMessage:
        "A daily count of how SurfSense is used, in ranges, and one more for each setup step in the first week. Never your documents, prompts or an ID.",
    }),
    details: intl.formatMessage(
      {
        id: "privacy_choices_usage_details_body",
        defaultMessage:
          "Once a day, SurfSense sends {host} the app’s version, your system and hardware, whether models can use your graphics card, and usage counts and days used, in ranges. Never documents, prompts, file names, model names, hosts, your license key or an ID.",
      },
      { host }
    ),
  }
}
