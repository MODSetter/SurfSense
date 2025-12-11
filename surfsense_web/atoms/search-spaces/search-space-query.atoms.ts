import { atomWithQuery } from "jotai-tanstack-query";
import { atom } from "jotai";
import type { GetSearchSpacesRequest } from "@/contracts/types/search-space.types";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

// Atom to store current query params for search spaces
export const searchSpacesQueryParamsAtom = atom<GetSearchSpacesRequest["queryParams"]>({
	page: 0,
	page_size: 10,
});

// Query atom to fetch search spaces with query params
export const searchSpacesAtom = atomWithQuery((get) => {
	const queryParams = get(searchSpacesQueryParamsAtom);

	return {
		queryKey: cacheKeys.searchSpaces.withQueryParams(queryParams),
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			return searchSpacesApiService.getSearchSpaces({
				queryParams,
			});
		},
	};
});
