import type { LocalRow } from "@/features/models/local/chat/api"
import type { ModelType } from "@/features/models/model-type"
import type { InUse } from "@/features/models/your-models/your-model-row"

/**
 * A step's models and how it chooses one: the seam between the chat step, whose
 * Use saves a selection, and the embedding step, whose Use only marks a choice
 * that Finish sends.
 */
export type StepModels = {
  /** The step's local rows: tested ones and anything already on disk. */
  rows: LocalRow[]
  /** What the rows were priced against, where the engine prices them at all. */
  hardware: string[] | null
  inUse: InUse | null
  isPending: boolean
  error: Error | null
  /** Choose an installed model by the name it runs under. */
  use: (name: string) => void
  choosing: boolean
  /** How a download from this step installs. */
  install: { select: boolean; modelType?: ModelType }
  /** What finishing onboarding from this step sends; null for the chat step. */
  value: string | null
}
