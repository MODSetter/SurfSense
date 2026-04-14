import { atom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import { newLLMConfigApiService } from "@/lib/apis/new-llm-config-api.service";
import { isCloud } from "@/lib/env-config";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/**
 * Query atom for fetching the system-managed LLM catalogue.
 * Only fetches in cloud mode (DEPLOYMENT_MODE=cloud).
 * Returns models with negative IDs configured in the backend YAML.
 */
export const systemModelsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.systemModels.all(),
		staleTime: 10 * 60 * 1000, // 10 minutes - system models rarely change
		enabled: isCloud(), // Only fetch when in cloud mode
		queryFn: async () => {
			return newLLMConfigApiService.getSystemModels();
		},
	};
});

/**
 * Atom holding the currently selected system model ID (negative integer).
 * null means no explicit selection — backend will use its default.
 *
 * NOTE: This is a global atom — it persists across search spaces within
 * a session. The ChatHeader component should reset it when needed.
 */
export const selectedSystemModelIdAtom = atom<number | null>(null);
