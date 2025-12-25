import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import type {
	CreateDocumentRequest,
	DeleteDocumentRequest,
	GetDocumentsResponse,
	UpdateDocumentRequest,
	UploadDocumentRequest,
} from "@/contracts/types/document.types";
import { trackDocumentDeleted, trackDocumentIndexed } from "@/lib/analytics";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { globalDocumentsQueryParamsAtom } from "./ui.atoms";

export const createDocumentMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!searchSpaceId,
		mutationFn: async (request: CreateDocumentRequest) => {
			return documentsApiService.createDocument(request);
		},

		onSuccess: (data, request: CreateDocumentRequest) => {
			// Track document creation/indexing
			if (searchSpaceId) {
				trackDocumentIndexed({
					search_space_id: Number(searchSpaceId),
					document_type: request.document_type,
				});
			}

			toast.success("Document created successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.typeCounts(searchSpaceId ?? undefined),
			});
		},
	};
});

export const uploadDocumentMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!searchSpaceId,
		mutationFn: async (request: UploadDocumentRequest) => {
			return documentsApiService.uploadDocument(request);
		},

		onSuccess: () => {
			toast.success("Files uploaded for processing");
		},
	};
});

export const updateDocumentMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!searchSpaceId,
		mutationFn: async (request: UpdateDocumentRequest) => {
			return documentsApiService.updateDocument(request);
		},

		onSuccess: (_, request: UpdateDocumentRequest) => {
			toast.success("Document updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.document(String(request.id)),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.typeCounts(searchSpaceId ?? undefined),
			});
		},
	};
});

export const deleteDocumentMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!searchSpaceId,
		mutationFn: async (request: DeleteDocumentRequest) => {
			return documentsApiService.deleteDocument(request);
		},

		onSuccess: (_, request: DeleteDocumentRequest) => {
			// Track document deletion
			if (searchSpaceId) {
				trackDocumentDeleted({
					search_space_id: Number(searchSpaceId),
					document_id: request.id,
				});
			}

			toast.success("Document deleted successfully");
			queryClient.setQueryData(
				cacheKeys.documents.globalQueryParams(documentsQueryParams),
				(oldData: GetDocumentsResponse | undefined) => {
					if (!oldData) return oldData;
					return {
						...oldData,
						items: oldData.items.filter((doc) => doc.id !== request.id),
						total: oldData.total - 1,
					};
				}
			);
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.document(String(request.id)),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.typeCounts(searchSpaceId ?? undefined),
			});
		},
	};
});
