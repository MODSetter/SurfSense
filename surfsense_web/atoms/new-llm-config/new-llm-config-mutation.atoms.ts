import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateNewLLMConfigRequest,
	CreateNewLLMConfigResponse,
	DeleteNewLLMConfigRequest,
	DeleteNewLLMConfigResponse,
	GetNewLLMConfigsResponse,
	UpdateLLMPreferencesRequest,
	UpdateNewLLMConfigRequest,
	UpdateNewLLMConfigResponse,
} from "@/contracts/types/new-llm-config.types";
import { newLLMConfigApiService } from "@/lib/apis/new-llm-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

/**
 * Mutation atom for creating a new NewLLMConfig
 */
export const createNewLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["new-llm-configs", "create"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: CreateNewLLMConfigRequest) => {
			return newLLMConfigApiService.createConfig(request);
		},
		onSuccess: (_: CreateNewLLMConfigResponse, request: CreateNewLLMConfigRequest) => {
			toast.success(`${request.name} created`);
			queryClient.invalidateQueries({
				queryKey: cacheKeys.newLLMConfigs.all(Number(searchSpaceId)),
			});
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to create LLM model");
		},
	};
});

/**
 * Mutation atom for updating an existing NewLLMConfig
 */
export const updateNewLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["new-llm-configs", "update"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateNewLLMConfigRequest) => {
			return newLLMConfigApiService.updateConfig(request);
		},
		onSuccess: (_: UpdateNewLLMConfigResponse, request: UpdateNewLLMConfigRequest) => {
			toast.success(`${request.data.name ?? "Configuration"} updated`);
			queryClient.invalidateQueries({
				queryKey: cacheKeys.newLLMConfigs.all(Number(searchSpaceId)),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.newLLMConfigs.byId(request.id),
			});
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to update");
		},
	};
});

/**
 * Mutation atom for deleting a NewLLMConfig
 */
export const deleteNewLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["new-llm-configs", "delete"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: DeleteNewLLMConfigRequest & { name: string }) => {
			return newLLMConfigApiService.deleteConfig({ id: request.id });
		},
		onSuccess: (
			_: DeleteNewLLMConfigResponse,
			request: DeleteNewLLMConfigRequest & { name: string }
		) => {
			toast.success(`${request.name} deleted`);
			queryClient.setQueryData(
				cacheKeys.newLLMConfigs.all(Number(searchSpaceId)),
				(oldData: GetNewLLMConfigsResponse | undefined) => {
					if (!oldData) return oldData;
					return oldData.filter((config) => config.id !== request.id);
				}
			);
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to delete");
		},
	};
});

/**
 * Mutation atom for updating LLM preferences (role assignments)
 */
export const updateLLMPreferencesMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["llm-preferences", "update"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateLLMPreferencesRequest) => {
			return newLLMConfigApiService.updateLLMPreferences(request);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: cacheKeys.newLLMConfigs.preferences(Number(searchSpaceId)),
			});
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to update LLM preferences");
		},
	};
});
