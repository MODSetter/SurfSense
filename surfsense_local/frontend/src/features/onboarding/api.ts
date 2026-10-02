import { requestJson } from "@/lib/api"

export type OnboardingStatus = {
  completed: boolean
}

export function getOnboardingStatus(
  signal?: AbortSignal
): Promise<OnboardingStatus> {
  return requestJson<OnboardingStatus>("/llm/onboarding", { signal })
}

/**
 * Ends onboarding and fixes the library's search model: the one named, already
 * downloaded, or the one SurfSense ships when none is.
 */
export function completeOnboarding(
  embeddingModel: string | null,
  signal?: AbortSignal
): Promise<OnboardingStatus> {
  return requestJson<OnboardingStatus>("/llm/onboarding", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ embedding_model: embeddingModel }),
    signal,
  })
}
