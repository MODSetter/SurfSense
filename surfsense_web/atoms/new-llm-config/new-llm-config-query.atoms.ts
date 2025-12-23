import { atomWithQuery } from "jotai-tanstack-query";
import { newLLMConfigApiService } from "@/lib/apis/new-llm-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

/**
 * Query atom for fetching all NewLLMConfigs for the active search space
 */
export const newLLMConfigsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.newLLMConfigs.all(Number(searchSpaceId)),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return newLLMConfigApiService.getConfigs({
				search_space_id: Number(searchSpaceId),
			});
		},
	};
});

/**
 * Query atom for fetching global NewLLMConfigs (from YAML, negative IDs)
 */
export const globalNewLLMConfigsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.newLLMConfigs.global(),
		staleTime: 10 * 60 * 1000, // 10 minutes - global configs rarely change
		queryFn: async () => {
			return newLLMConfigApiService.getGlobalConfigs();
		},
	};
});

/**
 * Query atom for fetching LLM preferences (role assignments) for the active search space
 */
export const llmPreferencesAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.newLLMConfigs.preferences(Number(searchSpaceId)),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return newLLMConfigApiService.getLLMPreferences(Number(searchSpaceId));
		},
	};
});

/**
 * Query atom for fetching default system instructions template
 */
export const defaultSystemInstructionsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.newLLMConfigs.defaultInstructions(),
		staleTime: 60 * 60 * 1000, // 1 hour - this rarely changes
		queryFn: async () => {
			return newLLMConfigApiService.getDefaultSystemInstructions();
		},
	};
});
