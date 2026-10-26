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
            "Once a day, SurfSense asks {host}, the update server your organization set, whether a newer version exists, sending your IP address, the app’s name and version, your operating system and its architecture, and no ID. A newer version downloads by itself from {host} and installs when you restart or the next time you quit.",
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
          "Once a day, SurfSense asks {host} whether a newer version exists, sending your IP address, the app’s name and version, your operating system and its architecture, and no ID. If {host} cannot answer, it asks github.com with only your IP address and the app’s name. A newer version downloads by itself from github.com and githubusercontent.com, which also see your IP address, and installs when you restart or the next time you quit.",
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
          "Once a day, SurfSense tells {host} this install was used, with the app’s version, your system, the app’s language and the week it was installed. During the install’s first week it sends one more each time setup reaches a new step, at most four more. Its reports in the first week, and one a week after that, add counts in ranges: chats, agent turns, sources, Studio outputs, plugin calls, whether a local or remote model answered, and how far setup got. Its first daily report adds this computer’s memory and graphics card, in ranges, and whether the model runtime can use the card; in the first week they go again only while part of them is unknown. Never documents, prompts, file names, model names, hosts, your license key or an ID.",
      },
      { host }
    ),
  }
}
