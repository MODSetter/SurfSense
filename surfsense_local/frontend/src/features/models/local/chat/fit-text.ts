import { intl } from "@/i18n/intl"

import type { Badge, Fit } from "./api"

// The codes are the backend's `SpeedTier` values, as `badge()` in
// modules/llm/fit/copy.py sends them; keep the two in sync. English mirrors
// that module's sentences, which stay the fallback for a code with no line
// here. `memory` is `unified` where the GPU shares the machine's memory.
const reducedSpeed = () =>
  intl.formatMessage({
    id: "models_fit_reduced_speed_label",
    defaultMessage: "Reduced speed",
  })

const verdictText: Record<string, () => string> = {
  too_big: () =>
    intl.formatMessage({
      id: "models_fit_too_big_label",
      defaultMessage: "Won’t fit",
    }),
  // One verdict for both; the line of why is what differs.
  heavy_spill: reducedSpeed,
  moderate_spill: reducedSpeed,
}

const reasonText: Record<
  string,
  (memory: "unified" | "separate", fit: Fit | null) => string | null
> = {
  too_big: (memory, fit) =>
    fit
      ? intl.formatMessage(
          {
            id: "models_fit_too_big_body",
            defaultMessage:
              "{memory, select, unified {Needs about {need, number, ::unit/gigabyte .#}. This Mac has {budget, number, ::unit/gigabyte .#}} other {Needs about {need, number, ::unit/gigabyte .#}. This PC has {budget, number, ::unit/gigabyte .#}}}",
          },
          {
            memory,
            need: fit.need_bytes / 1e9,
            budget: fit.budget_bytes / 1e9,
          }
        )
      : null,
  heavy_spill: (memory) =>
    intl.formatMessage(
      {
        id: "models_fit_heavy_spill_body",
        defaultMessage:
          "{memory, select, unified {Well over the GPU’s memory. Expect it to be slow.} other {Well over the graphics card’s memory. Expect it to be slow.}}",
      },
      { memory }
    ),
  moderate_spill: (memory) =>
    intl.formatMessage(
      {
        id: "models_fit_moderate_spill_body",
        defaultMessage:
          "{memory, select, unified {Too big for the GPU, so part runs on the CPU.} other {Too big for the graphics card, so part runs on the processor.}}",
      },
      { memory }
    ),
  light_spill: (memory) =>
    intl.formatMessage(
      {
        id: "models_fit_light_spill_body",
        defaultMessage:
          "{memory, select, unified {Most of it runs on the GPU.} other {Most of it runs on the graphics card.}}",
      },
      { memory }
    ),
}

/** The badge's word or two: the interface's for a tier it knows, else the backend's. */
export function fitVerdict(copy: Badge): string {
  const code = copy.code
  return code != null && Object.hasOwn(verdictText, code)
    ? verdictText[code]()
    : copy.verdict
}

/** The line of why, worded the same way. `fit` carries a refusal's two sizes. */
export function fitReason(copy: Badge, fit: Fit | null): string {
  const code = copy.code
  const own =
    code != null && Object.hasOwn(reasonText, code)
      ? reasonText[code](copy.uma ? "unified" : "separate", fit)
      : null
  return own ?? copy.reason
}
