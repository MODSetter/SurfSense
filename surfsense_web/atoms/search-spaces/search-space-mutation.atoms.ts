import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateSearchSpaceRequest,
	UpdateSearchSpaceRequest,
} from "@/contracts/types/search-space.types";
import { activeSearchSpaceIdAtom } from "./search-space-query.atoms";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const createSearchSpaceMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: ["create-search-space"],
		mutationFn: async (request: CreateSearchSpaceRequest) => {
			return searchSpacesApiService.createSearchSpace(request);
		},

		onSuccess: () => {
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
