import { requestJson } from "@/lib/api"

export type Destination = {
  destination: string
  host: string
  enabled: boolean
  last_call_at: string | null
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

export function describeDestination(destination: string, host: string) {
  if (destination === "app_updates") {
    return {
      label: "App updates",
      title: "Allow SurfSense to check for updates?",
      body: `Checking asks ${host} for the latest release. SurfSense sends your IP address and the version you are running, nothing else. Allowing also turns on the check at launch, which you can switch off in Settings › Network.`,
    }
  }
  // Searching, model weights and image weights are three errands to one host,
  // so this asks about the host once and names every errand. Search is the
  // widest of them and is stated first: it sends text as it is typed.
  if (destination === HUGGINGFACE) {
    return {
      label: "Model search and downloads",
      title: "Allow searching and downloading models?",
      body: `Searching sends what you type to ${host} as you type it. Downloading sends the name of the model you chose. Both send your IP address, and neither sends your chats or your documents.`,
    }
  }
  return {
    label: host,
    title: `Allow sending data to ${host}?`,
    body: `Chats using this connection send your prompts and excerpts of your documents to ${host}. You can turn this off any time in Settings › Network.`,
  }
}
