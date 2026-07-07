import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import type {
	CreateDocumentRequest,
	DeleteDocumentRequest,
	GetDocumentsResponse,
	UpdateDocumentRequest,
	UploadDocumentRequest,
} from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { globalDocumentsQueryParamsAtom } from "./ui.atoms";

export const createDocumentMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!workspaceId,
		mutationFn: async (request: CreateDocumentRequest) => {
			return documentsApiService.createDocument(request);
		},

		onSuccess: () => {
			toast.success("Document created successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
			});
		},
	};
});

export const uploadDocumentMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!workspaceId,
		mutationFn: async (request: UploadDocumentRequest) => {
			return documentsApiService.uploadDocument(request);
		},

		onSuccess: () => {
			// Note: Toast notification is handled by the caller (DocumentUploadTab) to use i18n
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(workspaceId ?? undefined),
			});
		},
	};
});

export const updateDocumentMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!workspaceId,
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
		},
	};
});

export const deleteDocumentMutationAtom = atomWithMutation((get) => {
	const workspaceId = get(activeWorkspaceIdAtom);
	const documentsQueryParams = get(globalDocumentsQueryParamsAtom);

	return {
		mutationKey: cacheKeys.documents.globalQueryParams(documentsQueryParams),
		enabled: !!workspaceId,
		mutationFn: async (request: DeleteDocumentRequest) => {
			return documentsApiService.deleteDocument(request);
		},

		onSuccess: (_, request: DeleteDocumentRequest) => {
			// Note: Toast is handled by the caller (page.tsx onBulkDelete) to show count info
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
		},
	};
});
