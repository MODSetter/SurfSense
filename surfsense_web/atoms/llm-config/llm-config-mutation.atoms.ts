import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
import type { CreateLLMConfigRequest, UpdateLLMConfigRequest } from "@/contracts/types/llm-config.types";
import { llmConfigApiService } from "@/lib/apis/llm-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

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

		onSuccess: (_, request: UpdateLLMConfigRequest) => {
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
