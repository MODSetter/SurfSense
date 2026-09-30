import { request, requestJson } from "@/lib/api"

const URL = "/llm/selection/audio_gen/voices"

/** The audio selection's voices: the server's own list, or the ones the user
 *  added after hearing each. `connection_id` and `model` play a voice. */
export type ServerVoicesRead = {
  connection_id: number
  model: string
  source: "server" | "saved"
  voices: string[]
  /** Where the provider documents the model's voices, when it does. */
  voices_page: string | null
}

export function readServerVoices(
  signal?: AbortSignal
): Promise<ServerVoicesRead> {
  return requestJson(URL, { signal })
}

/** Voices `text` in it first; the server's refusal keeps nothing. */
export async function addServerVoice({
  voice,
  text,
}: {
  voice: string
  text: string
}): Promise<void> {
  await request(URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ voice, text }),
  })
}

export async function removeServerVoice(voice: string): Promise<void> {
  await request(`${URL}?voice=${encodeURIComponent(voice)}`, {
    method: "DELETE",
  })
}
