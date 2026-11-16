import { useQuery } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "@/features/models/models-query"

import { readTranscriptionStatus } from "./api"

/** Under the models, so choosing or deleting a speech model reads it again. */
export const transcriptionStatusQueryKey = [
  ...MODELS_QUERY_KEY,
  "transcription",
  "status",
] as const

export function useTranscriptionStatus() {
  return useQuery({
    queryKey: transcriptionStatusQueryKey,
    queryFn: ({ signal }) => readTranscriptionStatus(signal),
  })
}

/** No speech model chosen yet: the mic sets one up instead of listening. */
export function useNeedsSpeechModel(): boolean {
  const status = useTranscriptionStatus()
  return (
    status.data?.ready === false && status.data.reason === "needs_speech_model"
  )
}
