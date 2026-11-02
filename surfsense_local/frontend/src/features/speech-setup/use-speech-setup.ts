import { useLocalSpeechCatalog } from "@/features/models/local/transcription/use-local-speech-catalog"

import { useSpeechDownload } from "./use-speech-download"

/**
 * Where setting up speech recognition stands. Choosing and downloading a model
 * happen in Settings › Speech recognition; this only says whether one is ready.
 */
export function useSpeechSetup() {
  const models = useLocalSpeechCatalog().data ?? []
  return {
    // A model on disk and chosen: recordings and voice input can use it.
    inUse: models.find((model) => model.selected && model.installed_as) ?? null,
    download: useSpeechDownload(),
  }
}
