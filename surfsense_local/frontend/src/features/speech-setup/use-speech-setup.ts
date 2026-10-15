import { useInstall } from "@/features/models/local/installs/use-install"
import { jobFor, jobsFor } from "@/features/models/local/installs/job-state"
import type { LocalSpeechModel } from "@/features/models/local/transcription/api"
import { useLocalSpeechCatalog } from "@/features/models/local/transcription/use-local-speech-catalog"
import { useSelect } from "@/features/models/selection/use-selection"

/**
 * Where setting up speech recognition stands, and the one step that does it.
 * Shared by the set-up popover and whatever opens it, so a waiting
 * recording's row and the mic read the same download.
 */
export function useSpeechSetup() {
  const catalog = useLocalSpeechCatalog()
  const { jobs, installs, install, cancel } = useInstall({
    select: true,
    modelType: "speech_to_text",
  })
  const select = useSelect("speech_to_text")
  const models = catalog.data ?? []

  // A model on disk and chosen: recordings and voice input can use it.
  const inUse =
    models.find((model) => model.selected && model.installed_as) ?? null

  const setUp = (model: LocalSpeechModel) => {
    if (model.installed_as) {
      void select
        .mutateAsync({
          target: {
            provider: "audiocpp",
            connection_id: null,
            name: model.installed_as,
          },
        })
        .catch(() => undefined)
    } else {
      void install(model.catalog_id)
    }
  }

  return {
    catalog,
    /** One card each; a model the user brought is chosen in Settings. */
    curated: models.filter((model) => model.curated),
    inUse,
    /** A speech download under way, wherever it was started. */
    download: jobsFor(installs, "speech_to_text")[0] ?? null,
    downloadOf: (model: LocalSpeechModel) =>
      jobFor(installs, model.catalog_id) ?? null,
    /** Downloaded and chosen, but the catalog has not said so yet. */
    settling: (model: LocalSpeechModel) =>
      catalog.isFetching &&
      jobs.some(
        (job) =>
          job.catalog_id === model.catalog_id && job.event.type === "complete"
      ),
    setUp,
    choosing: select.isPending,
    chooseError: select.error,
    cancel,
  }
}
