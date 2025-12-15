import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateLLMConfigRequest,
	DeleteLLMConfigRequest,
	GetLLMConfigsResponse,
	UpdateLLMConfigRequest,
	UpdateLLMConfigResponse,
	UpdateLLMPreferencesRequest,
} from "@/contracts/types/llm-config.types";
import { llmConfigApiService } from "@/lib/apis/llm-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

export const createLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: cacheKeys.llmConfigs.all(searchSpaceId!),
		enabled: !!searchSpaceId,
		mutationFn: async (request: CreateLLMConfigRequest) => {
			return llmConfigApiService.createLLMConfig(request);
		},

		onSuccess: () => {
			toast.success("LLM configuration created successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.all(searchSpaceId!),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.global(),
			});
		},
	};
});

export const updateLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: cacheKeys.llmConfigs.all(searchSpaceId!),
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateLLMConfigRequest) => {
			return llmConfigApiService.updateLLMConfig(request);
		},

		onSuccess: (_: UpdateLLMConfigResponse, request: UpdateLLMConfigRequest) => {
			toast.success("LLM configuration updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.all(searchSpaceId!),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.byId(String(request.id)),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.global(),
			});
		},
	};
});

export const deleteLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const authToken = localStorage.getItem("surfsense_bearer_token");

	return {
		mutationKey: cacheKeys.llmConfigs.all(searchSpaceId!),
		enabled: !!searchSpaceId && !!authToken,
		mutationFn: async (request: DeleteLLMConfigRequest) => {
			return llmConfigApiService.deleteLLMConfig(request);
		},

		onSuccess: (_, request: DeleteLLMConfigRequest) => {
			toast.success("LLM configuration deleted successfully");
			queryClient.setQueryData(
				cacheKeys.llmConfigs.all(searchSpaceId!),
				(oldData: GetLLMConfigsResponse | undefined) => {
					if (!oldData) return oldData;
					return oldData.filter((config) => config.id !== request.id);
				}
			);
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.byId(String(request.id)),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.global(),
			});
		},
	};
});

export const updateLLMPreferencesMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: cacheKeys.llmConfigs.preferences(searchSpaceId!),
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateLLMPreferencesRequest) => {
			return llmConfigApiService.updateLLMPreferences(request);
		},

		onSuccess: () => {
			toast.success("LLM preferences updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.llmConfigs.preferences(searchSpaceId!),
			});
		},
	};
});
