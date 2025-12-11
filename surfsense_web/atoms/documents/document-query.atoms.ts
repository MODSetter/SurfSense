import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import type { SearchDocumentsRequest } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { globalDocumentsQueryParamsAtom } from "./ui.atoms";

export const documentsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const queryParams = get(globalDocumentsQueryParamsAtom);

	return {
		queryKey: cacheKeys.documents.globalQueryParams(queryParams),
		enabled: !!searchSpaceId,
		queryFn: async () => {
			return documentsApiService.getDocuments({
				queryParams: queryParams,
			});
		},
	};
});

export const documentTypeCountsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.documents.typeCounts(searchSpaceId ?? undefined),
		enabled: !!searchSpaceId,
		staleTime: 10 * 60 * 1000, // 10 minutes
		queryFn: async () => {
			return documentsApiService.getDocumentTypeCounts({
				queryParams: {
					search_space_id: searchSpaceId ?? undefined,
				},
			});
		},
	};
});
