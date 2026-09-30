import { useQuery } from "@tanstack/react-query"

import { getProviders } from "../../chat-candidates/api"
import { MODELS_QUERY_KEY } from "../../models-query"

export const localRuntimeQueryKey = [
  ...MODELS_QUERY_KEY,
  "local",
  "runtime",
] as const

const LOCAL_RUNTIME = "llamacpp"

// llama-server restarts on every install and delete and can crash between
// them, so the answer is asked again every 15 s while the screen is open and
// whenever the window comes back, one local request each time.
const POLL_MS = 15_000

/** Whether llama-server answers, as `GET /llm/providers` last reported it. */
export function useLocalRuntime() {
  const providers = useQuery({
    queryKey: localRuntimeQueryKey,
    queryFn: ({ signal }) => getProviders(signal),
    refetchInterval: POLL_MS,
    refetchOnWindowFocus: true,
  })
  // Unknown is not down: the notice waits for an answer that says so.
  const available =
    providers.data?.find((p) => p.name === LOCAL_RUNTIME)?.healthy ?? true
  return { available }
}
