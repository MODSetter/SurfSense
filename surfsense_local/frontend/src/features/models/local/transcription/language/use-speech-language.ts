import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { MODELS_QUERY_KEY } from "../../../models-query"
import { readSpeechLanguage, writeSpeechLanguage } from "./api"

/** Keyed under the models: choosing another model drops the intent. */
export const speechLanguageQueryKey = [
  ...MODELS_QUERY_KEY,
  "speech",
  "language",
] as const

/** The intent and the languages the model is listed for, read only. */
export function useSpeechLanguageRead() {
  return useQuery({
    queryKey: speechLanguageQueryKey,
    queryFn: ({ signal }) => readSpeechLanguage(signal),
  })
}

export function useSpeechLanguage() {
  const client = useQueryClient()
  const language = useSpeechLanguageRead()
  const choose = useMutation({
    mutationFn: writeSpeechLanguage,
    onSuccess: (saved) => client.setQueryData(speechLanguageQueryKey, saved),
  })
  return { language, choose }
}
