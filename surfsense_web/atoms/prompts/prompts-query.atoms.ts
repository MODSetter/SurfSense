import { atomWithQuery } from "jotai-tanstack-query";
import { promptsApiService } from "@/lib/apis/prompts-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const promptsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.prompts.all(),
		staleTime: 5 * 60 * 1000,
		queryFn: async () => {
			return promptsApiService.list();
		},
	};
});

export const publicPromptsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.prompts.public(),
		staleTime: 2 * 60 * 1000,
		queryFn: async () => {
			return promptsApiService.listPublic();
		},
	};
});
