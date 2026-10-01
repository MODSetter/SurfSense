import type { ModelType } from "@/features/models/model-type"

import type { SlotModels } from "./use-slot-models"

/**
 * A step's models and how it chooses one: the seam between a slot, whose Use
 * saves a selection, and the embedding step, whose Use only marks a choice
 * that Finish sends.
 */
export type StepModels = SlotModels & {
  /** Choose an installed model by the name it runs under. */
  use: (name: string) => void
  choosing: boolean
  chooseError: Error | null
  /** How a download from this step installs. */
  install: { select: boolean; modelType?: ModelType }
  /** What finishing onboarding from this step sends; null for a slot. */
  value: string | null
}
