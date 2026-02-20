import { atomWithQuery } from "jotai-tanstack-query";
import type { LLMModel } from "@/contracts/enums/llm-models";
import { LLM_MODELS } from "@/contracts/enums/llm-models";
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

/**
 * Query atom for the dynamic LLM model catalogue.
 * Fetched from the backend (which proxies OpenRouter's public API).
 * Falls back to the static hardcoded list on error.
 */
export const modelListAtom = atomWithQuery(() => {
	return {
		queryKey: cacheKeys.newLLMConfigs.modelList(),
		staleTime: 60 * 60 * 1000, // 1 hour - models don't change often
		placeholderData: LLM_MODELS,
		queryFn: async (): Promise<LLMModel[]> => {
			const data = await newLLMConfigApiService.getModels();
			const dynamicModels = data.map((m) => ({
				value: m.value,
				label: m.label,
				provider: m.provider,
				contextWindow: m.context_window ?? undefined,
			}));

			// Providers covered by the dynamic API (from OpenRouter mapping).
			// For uncovered providers (Ollama, Groq, Bedrock, etc.) keep the
			// hand-curated static suggestions so users still see model options.
			const coveredProviders = new Set(dynamicModels.map((m) => m.provider));
			const staticFallbacks = LLM_MODELS.filter((m) => !coveredProviders.has(m.provider));

			return [...dynamicModels, ...staticFallbacks];
		},
	};
});
