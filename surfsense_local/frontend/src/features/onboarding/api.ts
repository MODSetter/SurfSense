import { requestJson } from "@/lib/api"

export type OnboardingStatus = {
  completed: boolean
}

export function getOnboardingStatus(
  signal?: AbortSignal
): Promise<OnboardingStatus> {
  return requestJson<OnboardingStatus>("/llm/onboarding", { signal })
}

export function completeOnboarding(
  signal?: AbortSignal
): Promise<OnboardingStatus> {
  return requestJson<OnboardingStatus>("/llm/onboarding", {
    method: "POST",
    signal,
  })
}
