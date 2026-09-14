import { requestJson } from "@/lib/api"

export type Destination = {
  destination: string
  host: string
  enabled: boolean
  last_call_at: string | null
}

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
  if (destination === "ollama_pull") {
    return {
      label: "Model downloads",
      title: "Allow model downloads?",
      body: `Downloading models contacts ${host}. SurfSense sends the model name and your IP address, nothing else.`,
    }
  }
  return {
    label: host,
    title: `Allow sending data to ${host}?`,
    body: `Chats using this connection send your prompts and excerpts of your documents to ${host}. You can turn this off any time in Settings › Network.`,
  }
}
