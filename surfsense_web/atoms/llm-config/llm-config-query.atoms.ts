import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
import { llmConfigApiService } from "@/lib/apis/llm-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const llmConfigsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.llmConfigs.all(searchSpaceId!),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return llmConfigApiService.getLLMConfigs({
				queryParams: {
					search_space_id: searchSpaceId!,
				},
			});
		},
	};
});

export const globalLLMConfigsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.llmConfigs.global(),
		staleTime: 10 * 60 * 1000, // 10 minutes
		queryFn: async () => {
			return llmConfigApiService.getGlobalLLMConfigs();
		},
	};
});

export const llmPreferencesAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.llmConfigs.preferences(String(searchSpaceId)),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return llmConfigApiService.getLLMPreferences({
				search_space_id: Number(searchSpaceId),
			});
		},
	};
});
