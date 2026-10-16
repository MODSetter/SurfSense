import { intl } from "@/i18n/intl"
import { requestJson } from "@/lib/api"

export type Destination = {
  destination: string
  host: string
  enabled: boolean
  last_call_at: string | null
}

/** Switch on a question's destination and every other host it named. */
export async function allowAll(destination: string, also: string[] = []) {
  await setDestinationEnabled(destination, true)
  for (const host of also) await setDestinationEnabled(`host:${host}`, true)
}

/** Search, model weights and image weights all reach this one host. */
export const HUGGINGFACE = "host:huggingface.co"

export const destinationsQueryKey = ["egress"] as const

export function listDestinations(signal?: AbortSignal): Promise<Destination[]> {
  return requestJson<Destination[]>("/egress", { signal })
}

export function setDestinationEnabled(
  destination: string,
  enabled: boolean
): Promise<Destination> {
  return requestJson<Destination>(`/egress/${destination}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  })
}

// A Claude plan's two hosts: model calls, and where Claude Code refreshes its sign-in.
const CLAUDE_API_HOST = "api.anthropic.com"
const CLAUDE_SIGN_IN_HOST = "platform.claude.com"

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
  return {
    ...one,
    details: also.length
      ? [
          intl.formatMessage(
            {
              id: "egress_prompt_also_allows_body",
              defaultMessage: "Allowing also lets SurfSense reach {hosts}.",
            },
            { hosts: intl.formatList(also, { type: "conjunction" }) }
          ),
        ]
      : [],
  }
}

// Each host's own sentence, since one gets chats and the other only a sign-in.
function describeClaudePlan(hosts: string[]): DestinationCopy {
  const details = []
  if (hosts.includes(CLAUDE_API_HOST))
    details.push(
      intl.formatMessage(
        {
          id: "egress_claude_api_host_body",
          defaultMessage:
            "{host} gets what you send the model: your prompts and excerpts of your documents.",
        },
        { host: CLAUDE_API_HOST }
      )
    )
  if (hosts.includes(CLAUDE_SIGN_IN_HOST))
    details.push(
      intl.formatMessage(
        {
          id: "egress_claude_sign_in_host_body",
          defaultMessage:
            "{host} keeps Claude Code signed in. It gets no chats, and turning it off stops Claude once the sign-in expires.",
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
        "Claude Code on this computer reaches Anthropic only through SurfSense, and only the hosts you allow. You can turn each one off in Settings › Network.",
    }),
    details,
  }
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
      body: intl.formatMessage(
        {
          id: "egress_app_updates_prompt_body",
          defaultMessage:
            "Checking asks {host} for the latest release. SurfSense sends your IP address and the version you are running, nothing else. Allowing also turns on the check at launch, which you can switch off in Settings › Network.",
        },
        { host }
      ),
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
  // The registry's host is also SurfSense's own plugins', so one answer covers both.
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
            "SurfSense fetches the list of third-party plugins from {host}, sending your IP address and nothing else. SurfSense’s own plugins run on the same host, so this also lets you connect them. You can turn this off any time in Settings › Network.",
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
