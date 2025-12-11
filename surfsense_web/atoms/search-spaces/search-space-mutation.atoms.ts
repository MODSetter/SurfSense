import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateSearchSpaceRequest,
} from "@/contracts/types/search-space.types";
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
