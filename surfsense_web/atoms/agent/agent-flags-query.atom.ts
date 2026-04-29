import { atomWithQuery } from "jotai-tanstack-query";
import { agentFlagsApiService } from "@/lib/apis/agent-flags-api.service";
import { getBearerToken } from "@/lib/auth-utils";

export const AGENT_FLAGS_QUERY_KEY = ["agent", "flags"] as const;

/**
 * Reads the backend agent feature flags. Cached for the lifetime of the
 * page (flags only change on backend restart) so we can drive UI gating
 * without re-hitting the API.
 */
export const agentFlagsAtom = atomWithQuery(() => ({
	queryKey: AGENT_FLAGS_QUERY_KEY,
	staleTime: 10 * 60 * 1000,
	enabled: !!getBearerToken(),
	queryFn: () => agentFlagsApiService.get(),
}));
