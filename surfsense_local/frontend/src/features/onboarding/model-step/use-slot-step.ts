import { useSelect } from "@/features/models/selection/use-selection"

import { LOCAL_PROVIDER, type OnboardingSlot } from "./slot"
import type { StepModels } from "./step-models"
import { slotModels } from "./use-slot-models"

/** A slot's step: Use saves the selection, and a download becomes it. */
export function useSlotStep(slot: OnboardingSlot): StepModels {
  const models = slotModels[slot]()
  const select = useSelect(slot)
  return {
    ...models,
    use: (name) =>
      void select
        .mutateAsync({
          target: {
            provider: LOCAL_PROVIDER[slot],
            connection_id: null,
            name,
          },
        })
        .catch(() => undefined),
    choosing: select.isPending,
    chooseError: select.isError ? select.error : null,
    install: { select: true, modelType: slot },
    value: null,
  }
}
