import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateSearchSpaceRequest,
	DeleteSearchSpaceRequest,
	UpdateSearchSpaceRequest,
} from "@/contracts/types/search-space.types";
import { trackSearchSpaceCreated, trackSearchSpaceDeleted } from "@/lib/analytics";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeSearchSpaceIdAtom } from "./search-space-query.atoms";

export const createSearchSpaceMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: ["create-search-space"],
		mutationFn: async (request: CreateSearchSpaceRequest) => {
			return searchSpacesApiService.createSearchSpace(request);
		},

		onSuccess: (data, request: CreateSearchSpaceRequest) => {
			// Track search space creation
			trackSearchSpaceCreated({ search_space_id: data.id, name: request.name });

			toast.success("Search space created successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.searchSpaces.all,
			});
		},
	};
});

export const updateSearchSpaceMutationAtom = atomWithMutation((get) => {
	const activeSearchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["update-search-space", activeSearchSpaceId],
		enabled: !!activeSearchSpaceId,
		mutationFn: async (request: UpdateSearchSpaceRequest) => {
			return searchSpacesApiService.updateSearchSpace(request);
		},

		onSuccess: (_, request: UpdateSearchSpaceRequest) => {
			toast.success("Search space updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.searchSpaces.all,
			});
			if (request.id) {
				queryClient.invalidateQueries({
					queryKey: cacheKeys.searchSpaces.detail(String(request.id)),
				});
			}
		},
	};
});

export const deleteSearchSpaceMutationAtom = atomWithMutation((get) => {
	const activeSearchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		mutationKey: ["delete-search-space", activeSearchSpaceId],
		enabled: !!activeSearchSpaceId,
		mutationFn: async (request: DeleteSearchSpaceRequest) => {
			return searchSpacesApiService.deleteSearchSpace(request);
		},

		onSuccess: (_, request: DeleteSearchSpaceRequest) => {
			// Track search space deletion
			if (request.id) {
				trackSearchSpaceDeleted({ search_space_id: request.id });
			}

			toast.success("Search space deleted successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.searchSpaces.all,
			});
			if (request.id) {
				queryClient.removeQueries({
					queryKey: cacheKeys.searchSpaces.detail(String(request.id)),
				});
			}
		},
	};
});
