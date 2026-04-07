import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateVisionLLMConfigRequest,
	CreateVisionLLMConfigResponse,
	DeleteVisionLLMConfigResponse,
	GetVisionLLMConfigsResponse,
	UpdateVisionLLMConfigRequest,
	UpdateVisionLLMConfigResponse,
} from "@/contracts/types/new-llm-config.types";
import { visionLLMConfigApiService } from "@/lib/apis/vision-llm-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

export const createVisionLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["vision-llm-configs", "create"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: CreateVisionLLMConfigRequest) => {
			return visionLLMConfigApiService.createConfig(request);
		},
		onSuccess: (_: CreateVisionLLMConfigResponse, request: CreateVisionLLMConfigRequest) => {
			toast.success(`${request.name} created`);
			queryClient.invalidateQueries({
				queryKey: cacheKeys.visionLLMConfigs.all(Number(searchSpaceId)),
			});
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to create vision model");
		},
	};
});

export const updateVisionLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["vision-llm-configs", "update"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateVisionLLMConfigRequest) => {
			return visionLLMConfigApiService.updateConfig(request);
		},
		onSuccess: (_: UpdateVisionLLMConfigResponse, request: UpdateVisionLLMConfigRequest) => {
			toast.success(`${request.data.name ?? "Configuration"} updated`);
			queryClient.invalidateQueries({
				queryKey: cacheKeys.visionLLMConfigs.all(Number(searchSpaceId)),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.visionLLMConfigs.byId(request.id),
			});
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to update vision model");
		},
	};
});

export const deleteVisionLLMConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["vision-llm-configs", "delete"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: { id: number; name: string }) => {
			return visionLLMConfigApiService.deleteConfig(request.id);
		},
		onSuccess: (_: DeleteVisionLLMConfigResponse, request: { id: number; name: string }) => {
			toast.success(`${request.name} deleted`);
			queryClient.setQueryData(
				cacheKeys.visionLLMConfigs.all(Number(searchSpaceId)),
				(oldData: GetVisionLLMConfigsResponse | undefined) => {
					if (!oldData) return oldData;
					return oldData.filter((config) => config.id !== request.id);
				}
			);
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to delete vision model");
		},
	};
});
