import { useState } from "react"

import { useLocalChatCatalog } from "@/features/models/local/chat/use-local-chat-catalog"
import { intl } from "@/i18n/intl"

import { leadBuild } from "./local-choices"
import type { StepModels } from "./step-models"

/**
 * The embedding step: the choice is held here and sent by Finish, never saved
 * as a selection. The model SurfSense ships is in use until another is used,
 * and again if that one is deleted.
 */
export function useEmbeddingStep(): StepModels {
  const [chosen, setChosen] = useState<string | null>(null)
  const catalog = useLocalChatCatalog()
  const embedders = (catalog.data?.rows ?? []).filter(
    (row) => row.engine === "onnxruntime"
  )
  const picked = embedders.find(
    (row) => row.id === chosen && leadBuild(row)?.installed_as != null
  )
  const current =
    picked ?? embedders.find((row) => leadBuild(row)?.bundled === true)
  const build = current ? leadBuild(current) : null

  return {
    // Marked as a slot's model is, so the chosen row reads "In use"; a
    // Hugging Face pick says nobody measured it.
    rows: embedders.map((row) => ({
      ...row,
      description:
        row.description ??
        (row.origin === "downloaded"
          ? intl.formatMessage({
              id: "onboarding_embedding_step_untested_label",
              defaultMessage: "Not tested by SurfSense",
            })
          : null),
      builds: row.builds.map((each) => ({
        ...each,
        selected: row.id === current?.id,
      })),
    })),
    // Embedders are small; nothing to say about the machine.
    hardware: null,
    inUse:
      current && build?.installed_as
        ? { name: current.name, source: build.quantization, where: "local" }
        : null,
    isPending: catalog.isPending,
    error: catalog.error,
    use: setChosen,
    choosing: false,
    chooseError: null,
    // An embedder is never a selection, so a download selects nothing.
    install: { select: false },
    value: picked?.id ?? null,
  }
}
