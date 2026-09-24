import { createInstall } from "@/features/models/local/create-install"

import type { OnboardingSlot } from "./slot"

/**
 * Onboarding selects what it installs, so a first model takes one click. Each
 * slot keeps its own store, so a chat download never shows on the image step.
 */
export const onboardingInstalls: Record<
  OnboardingSlot,
  ReturnType<typeof createInstall>
> = {
  text_gen: createInstall({ select: true }),
  image_gen: createInstall({ select: true }),
}
