import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateImageGenConfigRequest,
	GetImageGenConfigsResponse,
	UpdateImageGenConfigRequest,
	UpdateImageGenConfigResponse,
} from "@/contracts/types/new-llm-config.types";
import { imageGenConfigApiService } from "@/lib/apis/image-gen-config-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "../search-spaces/search-space-query.atoms";

/**
 * Mutation atom for creating a new ImageGenerationConfig
 */
export const createImageGenConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["image-gen-configs", "create"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: CreateImageGenConfigRequest) => {
			return imageGenConfigApiService.createConfig(request);
		},
		onSuccess: () => {
			toast.success("Image model configuration created");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.imageGenConfigs.all(Number(searchSpaceId)),
			});
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to create image model configuration");
		},
	};
});

/**
 * Mutation atom for updating an existing ImageGenerationConfig
 */
export const updateImageGenConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["image-gen-configs", "update"],
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateImageGenConfigRequest) => {
			return imageGenConfigApiService.updateConfig(request);
		},
		onSuccess: (_: UpdateImageGenConfigResponse, request: UpdateImageGenConfigRequest) => {
			toast.success("Image model configuration updated");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.imageGenConfigs.all(Number(searchSpaceId)),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.imageGenConfigs.byId(request.id),
			});
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to update image model configuration");
		},
	};
});

/**
 * Mutation atom for deleting an ImageGenerationConfig
 */
export const deleteImageGenConfigMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["image-gen-configs", "delete"],
		enabled: !!searchSpaceId,
		mutationFn: async (id: number) => {
			return imageGenConfigApiService.deleteConfig(id);
		},
		onSuccess: (_, id: number) => {
			toast.success("Image model configuration deleted");
			queryClient.setQueryData(
				cacheKeys.imageGenConfigs.all(Number(searchSpaceId)),
				(oldData: GetImageGenConfigsResponse | undefined) => {
					if (!oldData) return oldData;
					return oldData.filter((config) => config.id !== id);
				}
			);
		},
		onError: (error: Error) => {
			toast.error(error.message || "Failed to delete image model configuration");
		},
	};
});
