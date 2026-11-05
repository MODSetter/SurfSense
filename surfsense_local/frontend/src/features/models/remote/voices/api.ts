import { request, requestJson } from "@/lib/api"

const URL = "/llm/selection/audio_gen/voices"

/** A voice's id, and its name where the server states one, else the id again. */
export type VoiceOption = { id: string; label: string }

/** The audio selection's voices: the server's own list; the model's published
 *  ones and those the user added; or the added ones alone. `connection_id` and
 *  `model` play a voice. */
export type ServerVoicesRead = {
  connection_id: number
  model: string
  source: "server" | "published" | "saved"
  voices: VoiceOption[]
  /** The ones removing can take away; the rest are the server's. */
  added: string[]
  /** Where the provider documents the model's voices, when it does. */
  voices_page: string | null
  /** Why there is no list to offer, when it is not that the server has none. */
  problem?: { code: "no_usable_voices" | "list_failed"; message: string } | null
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
