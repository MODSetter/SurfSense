import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
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

export const getDocumentAtom = (documentId: number) =>
	atomWithQuery(() => {
		return {
			queryKey: cacheKeys.documents.document(String(documentId)),
			enabled: !!documentId,
			queryFn: async () => {
				if (!documentId) {
					throw new Error("No active document id found");
				}

				return documentsApiService.getDocument({ id: documentId });
			},
		};
	});

export const documentTypeCountsAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.documents.typeCounts(searchSpaceId ?? undefined),
		enabled: !!searchSpaceId,
		queryFn: async () => {
			return documentsApiService.getDocumentTypeCounts({
				queryParams: {
					search_space_id: searchSpaceId ?? undefined,
				},
			});
		},
	};
});

export const getDocumentByChunkAtom = (chunkId: number) =>
	atomWithQuery(() => {
		return {
			queryKey: cacheKeys.documents.byChunk(String(chunkId)),
			enabled: !!chunkId,
			queryFn: async () => {
				if (!chunkId) {
					throw new Error("No active chunk id found");
				}

				return documentsApiService.getDocumentByChunk({ chunk_id: chunkId });
			},
		};
	});

export const searchDocumentsAtom = (request: SearchDocumentsRequest) =>
	atomWithQuery((get) => {
		const searchSpaceId = get(activeSearchSpaceIdAtom);

		return {
			queryKey: cacheKeys.documents.globalQueryParams(request.queryParams),
			enabled: !!searchSpaceId,
			queryFn: async () => {
				return documentsApiService.searchDocuments({
					...request,
					queryParams: {
						...request.queryParams,
						search_space_id: searchSpaceId ?? undefined,
					},
				});
			},
		};
	});
