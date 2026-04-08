import { atomWithQuery } from "jotai-tanstack-query";
import type { LLMModel } from "@/contracts/enums/llm-models";
import { VISION_MODELS } from "@/contracts/enums/vision-providers";
import { visionLLMConfigApiService } from "@/lib/apis/vision-llm-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

export const visionLLMConfigsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.visionLLMConfigs.all(Number(searchSpaceId)),
		enabled: !!searchSpaceId,
		staleTime: 5 * 60 * 1000,
		queryFn: async () => {
			return visionLLMConfigApiService.getConfigs(Number(searchSpaceId));
		},
	};
});

export const globalVisionLLMConfigsAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.visionLLMConfigs.global(),
		staleTime: 10 * 60 * 1000,
		queryFn: async () => {
			return visionLLMConfigApiService.getGlobalConfigs();
		},
	};
});

export const visionModelListAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.visionLLMConfigs.modelList(),
		staleTime: 60 * 60 * 1000,
		placeholderData: VISION_MODELS,
		queryFn: async (): Promise<LLMModel[]> => {
			const data = await visionLLMConfigApiService.getModels();
			const dynamicModels = data.map((m) => ({
				value: m.value,
				label: m.label,
				provider: m.provider,
				contextWindow: m.context_window ?? undefined,
			}));

			const coveredProviders = new Set(dynamicModels.map((m) => m.provider));
			const staticFallbacks = VISION_MODELS.filter((m) => !coveredProviders.has(m.provider));

			return [...dynamicModels, ...staticFallbacks];
		},
	};
});
