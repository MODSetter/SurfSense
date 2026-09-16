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
  if (destination === "app_updates") {
    return {
      label: "App updates",
      title: "Allow SurfSense to check for updates?",
      body: `Checking asks ${host} for the latest release. SurfSense sends your IP address and the version you are running, nothing else. Allowing also turns on the check at launch, which you can switch off in Settings › Network.`,
    }
  }
  if (destination === "ollama_pull") {
    return {
      label: "Model downloads",
      title: "Allow model downloads?",
      body: `Downloading models contacts ${host}. SurfSense sends the model name and your IP address, nothing else.`,
    }
  }
  if (destination === "image_model_pull") {
    return {
      label: "Image model downloads",
      title: "Allow image model downloads?",
      body: `Downloading an image model contacts ${host}. SurfSense sends the model name and your IP address, nothing else. The model then generates on this computer.`,
    }
  }
  return {
    label: host,
    title: `Allow sending data to ${host}?`,
    body: `Chats using this connection send your prompts and excerpts of your documents to ${host}. You can turn this off any time in Settings › Network.`,
  }
}
