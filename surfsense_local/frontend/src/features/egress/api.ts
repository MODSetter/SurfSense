import { intl } from "@/i18n/intl"
import { requestJson } from "@/lib/api"

export type Destination = {
  destination: string
  host: string
  enabled: boolean
  last_call_at: string | null
}

/**
 * Switch on a question's destination and every other host it named, in one
 * request the API commits whole: a failed Allow switches none of them on.
 */
export function allowAll(destination: string, also: string[] = []) {
  return setDestinationsEnabled(
    [destination, ...also.map((host) => `host:${host}`)],
    true
  )
}

/** Search, model weights and image weights all reach this one host. */
export const HUGGINGFACE = "host:huggingface.co"

export const destinationsQueryKey = ["egress"] as const

export function listDestinations(signal?: AbortSignal): Promise<Destination[]> {
  return requestJson<Destination[]>("/egress", { signal })
}

/** Switch these destinations on or off together; one row in Settings › Network is a list of one. */
export function setDestinationsEnabled(
  destinations: string[],
  enabled: boolean
): Promise<Destination[]> {
  return requestJson<Destination[]>("/egress", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ destinations, enabled }),
  })
}

// A Claude plan's two hosts: model calls, and where Claude Code refreshes its sign-in.
const CLAUDE_API_HOST = "api.anthropic.com"
const CLAUDE_SIGN_IN_HOST = "platform.claude.com"

// SurfSense's own plugins: the one host the license key is ever sent to.
const SURFSENSE_PLUGIN_HOST = "plugins.surfsense.com"

export type DestinationCopy = {
  label: string
  title: string
  body: string
  /** Whole sentences shown after the body, one paragraph each. */
  details: string[]
}

/**
 * How a destination is named in Settings › Network, and the question asked
 * before allowing it. `also` names the other hosts asked about in the same
 * question, which one Allow switches on together.
 */
export function describeDestination(
  destination: string,
  host: string,
  purpose?: string,
  also: string[] = []
): DestinationCopy {
  if (purpose === "claude_plan" || host === CLAUDE_SIGN_IN_HOST)
    return describeClaudePlan([host, ...also])
  const one = describeOne(destination, host, purpose)
  const details = []
  if (also.length)
    details.push(
      intl.formatMessage(
        {
          id: "egress_prompt_also_allows_body",
          defaultMessage: "Allowing also lets SurfSense reach {hosts}.",
        },
        { hosts: intl.formatList(also, { type: "conjunction" }) }
      )
    )
  // The registry's own copy already says this; a plugin's does not.
  if (purpose === "plugin" && [host, ...also].includes(SURFSENSE_PLUGIN_HOST))
    details.push(
      intl.formatMessage(
        {
          id: "egress_plugin_license_body",
          defaultMessage:
            "For SurfSense’s paid plugins, {host} also gets your license key, so the service can check it.",
        },
        { host: SURFSENSE_PLUGIN_HOST }
      )
    )
  return { ...one, details }
}

// Each host's own sentence, since one gets chats and the other only a sign-in.
function describeClaudePlan(hosts: string[]): DestinationCopy {
  const details = []
  if (hosts.includes(CLAUDE_API_HOST))
    details.push(
      intl.formatMessage(
        {
          id: "egress_claude_api_host_body",
          defaultMessage: "{host} gets your prompts and document excerpts.",
        },
        { host: CLAUDE_API_HOST }
      )
    )
  if (hosts.includes(CLAUDE_SIGN_IN_HOST))
    details.push(
      intl.formatMessage(
        {
          id: "egress_claude_sign_in_host_body",
          defaultMessage: "{host} only refreshes Claude Code’s sign-in.",
        },
        { host: CLAUDE_SIGN_IN_HOST }
      )
    )
  return {
    label:
      hosts[0] === CLAUDE_SIGN_IN_HOST
        ? intl.formatMessage({
            id: "egress_claude_sign_in_label",
            defaultMessage: "Claude Code sign-in",
          })
        : hosts[0],
    title: intl.formatMessage({
      id: "egress_claude_prompt_title",
      defaultMessage: "Allow your Claude plan to reach Anthropic?",
    }),
    body: intl.formatMessage({
      id: "egress_claude_prompt_body",
      defaultMessage:
        "Claude Code reaches only the hosts you allow, through SurfSense. Turn each off in Settings › Network.",
    }),
    details,
  }
}

// An admin policy's mirror never falls back to GitHub and serves the download
// too; an Electron main without the privacy bridge reads GitHub's releases alone.
function updatesBody(host: string, purpose?: string) {
  if (purpose === "update_mirror")
    return intl.formatMessage(
      {
        id: "egress_app_updates_mirror_prompt_body",
        defaultMessage:
          "Once a day, SurfSense asks {host}, the update server your organization set, whether a newer version exists. The request sends your IP address, the app’s name and version, your operating system and its architecture, and no ID. A newer version downloads from {host} and installs when you restart from the prompt or the next time you quit. Allowing also turns on the daily check, which you can switch off in Settings › Network.",
      },
      { host }
    )
  if (purpose === "github_releases")
    return intl.formatMessage(
      {
        id: "egress_app_updates_github_prompt_body",
        defaultMessage:
          "A check reads the list of releases on {host}, then asks for the release file for your platform: Windows, macOS or Linux. It sends your IP address and identifies itself only as electron-builder, with no version and no ID. GitHub serves its release files from githubusercontent.com, which also sees your IP address. A newer version downloads on its own and installs when you restart from the prompt or the next time you quit. Allowing also turns on the check at launch, which you can switch off in Settings › Network.",
      },
      { host }
    )
  return intl.formatMessage(
    {
      id: "egress_app_updates_prompt_body",
      defaultMessage:
        "Once a day, SurfSense asks {host} whether a newer version exists. The request sends your IP address, the app’s name and version, your operating system and its architecture, and no ID. If {host} cannot answer, SurfSense asks github.com instead, sending only your IP address and the app’s name. A newer version downloads from github.com, whose download host, githubusercontent.com, also sees your IP address. It installs when you restart from the prompt or the next time you quit. Allowing also turns on the daily check, which you can switch off in Settings › Network.",
    },
    { host }
  )
}

function describeOne(destination: string, host: string, purpose?: string) {
  if (destination === "app_updates") {
    return {
      label: intl.formatMessage({
        id: "egress_app_updates_label",
        defaultMessage: "App updates",
      }),
      title: intl.formatMessage({
        id: "egress_app_updates_prompt_title",
        defaultMessage: "Allow SurfSense to check for updates?",
      }),
      body: updatesBody(host, purpose),
    }
  }
  // Searching, model weights and image weights are three errands to one host,
  // so this asks about the host once and names every errand. Search is the
  // widest of them and is stated first: it sends text as it is typed.
  if (destination === HUGGINGFACE) {
    return {
      label: intl.formatMessage({
        id: "egress_huggingface_label",
        defaultMessage: "Model search and downloads",
      }),
      title: intl.formatMessage({
        id: "egress_huggingface_prompt_title",
        defaultMessage: "Allow searching and downloading models?",
      }),
      body: intl.formatMessage(
        {
          id: "egress_huggingface_prompt_body",
          defaultMessage:
            "Searching sends what you type to {host} as you type it. Downloading sends the name of the model you chose. Both send your IP address, and neither sends your chats or your documents.",
        },
        { host }
      ),
    }
  }
  // Office support's download is the only errand to The Document Foundation.
  if (
    host === "documentfoundation.org" ||
    host.endsWith(".documentfoundation.org")
  ) {
    return {
      label: intl.formatMessage({
        id: "egress_office_download_label",
        defaultMessage: "Office support download",
      }),
      title: intl.formatMessage({
        id: "egress_office_download_prompt_title",
        defaultMessage: "Allow downloading LibreOffice?",
      }),
      body: intl.formatMessage(
        {
          id: "egress_office_download_prompt_body",
          defaultMessage:
            "Turning on Office support downloads LibreOffice from {host}. SurfSense sends your IP address and the file’s name, nothing else.",
        },
        { host }
      ),
    }
  }
  // The registry's host is also SurfSense's own plugins', so one answer covers
  // both, and says what using them sends.
  if (purpose === "plugin_registry") {
    return {
      label: host,
      title: intl.formatMessage({
        id: "egress_plugin_registry_prompt_title",
        defaultMessage: "Allow fetching the list of plugins?",
      }),
      body: intl.formatMessage(
        {
          id: "egress_plugin_registry_prompt_body",
          defaultMessage:
            "SurfSense fetches the list of third-party plugins from {host}, sending your IP address and nothing else. SurfSense’s own plugins run on the same host, so this also lets you connect them. Using them sends {host} what each tool needs and, for the paid ones, your license key so the service can check it. You can turn this off any time in Settings › Network.",
        },
        { host }
      ),
    }
  }
  // A plugin's server gets what its tools are sent, never every chat.
  if (purpose === "plugin") {
    return {
      label: host,
      title: intl.formatMessage(
        {
          id: "egress_plugin_prompt_title",
          defaultMessage: "Allow connecting to {host}?",
        },
        { host }
      ),
      body: intl.formatMessage(
        {
          id: "egress_plugin_prompt_body",
          defaultMessage:
            "{host} runs a plugin’s server. SurfSense contacts it to list its tools, and the agent sends it what a tool you allow needs, along with your IP address. You can turn this off any time in Settings › Network.",
        },
        { host }
      ),
    }
  }
  return {
    label: host,
    title: intl.formatMessage(
      {
        id: "egress_connection_prompt_title",
        defaultMessage: "Allow sending data to {host}?",
      },
      { host }
    ),
    body: intl.formatMessage(
      {
        id: "egress_connection_prompt_body",
        defaultMessage:
          "Chats using this connection send your prompts and excerpts of your documents to {host}. You can turn this off any time in Settings › Network.",
      },
      { host }
    ),
  }
}
