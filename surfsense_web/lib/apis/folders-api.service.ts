import {
	type BulkDocumentMoveRequest,
	bulkDocumentMoveRequest,
	type DocumentMoveRequest,
	documentMoveRequest,
	type FolderCreateRequest,
	type FolderMoveRequest,
	type FolderReorderRequest,
	type FolderUpdateRequest,
	folder,
	folderBreadcrumbResponse,
	folderCreateRequest,
	folderDeleteResponse,
	folderListResponse,
	folderMoveRequest,
	folderReorderRequest,
	folderUpdateRequest,
} from "@/contracts/types/folder.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class FoldersApiService {
	createFolder = async (request: FolderCreateRequest) => {
		const parsed = folderCreateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(
				`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
			);
		}
		return baseApiService.post("/api/v1/folders", folder, { body: parsed.data });
	};

	listFolders = async (searchSpaceId: number) => {
		return baseApiService.get(
			`/api/v1/folders?search_space_id=${searchSpaceId}`,
			folderListResponse
		);
	};

	getFolder = async (folderId: number) => {
		return baseApiService.get(`/api/v1/folders/${folderId}`, folder);
	};

	getFolderBreadcrumb = async (folderId: number) => {
		return baseApiService.get(`/api/v1/folders/${folderId}/breadcrumb`, folderBreadcrumbResponse);
	};

	updateFolder = async (folderId: number, request: FolderUpdateRequest) => {
		const parsed = folderUpdateRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(
				`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
			);
		}
		return baseApiService.put(`/api/v1/folders/${folderId}`, folder, {
			body: parsed.data,
		});
	};

	moveFolder = async (folderId: number, request: FolderMoveRequest) => {
		const parsed = folderMoveRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(
				`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
			);
		}
		return baseApiService.put(`/api/v1/folders/${folderId}/move`, folder, {
			body: parsed.data,
		});
	};

	reorderFolder = async (folderId: number, request: FolderReorderRequest) => {
		const parsed = folderReorderRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(
				`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
			);
		}
		return baseApiService.put(`/api/v1/folders/${folderId}/reorder`, folder, {
			body: parsed.data,
		});
	};

	deleteFolder = async (folderId: number) => {
		return baseApiService.delete(`/api/v1/folders/${folderId}`, folderDeleteResponse);
	};

	stopWatching = async (folderId: number) => {
		return baseApiService.patch(`/api/v1/folders/${folderId}/watched`, undefined);
	};

	moveDocument = async (documentId: number, request: DocumentMoveRequest) => {
		const parsed = documentMoveRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(
				`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
			);
		}
		return baseApiService.put(`/api/v1/documents/${documentId}/move`, undefined, {
			body: parsed.data,
		});
	};

	bulkMoveDocuments = async (request: BulkDocumentMoveRequest) => {
		const parsed = bulkDocumentMoveRequest.safeParse(request);
		if (!parsed.success) {
			throw new ValidationError(
				`Invalid request: ${parsed.error.issues.map((i) => i.message).join(", ")}`
			);
		}
		return baseApiService.put("/api/v1/documents/bulk-move", undefined, {
			body: parsed.data,
		});
	};
}

export const foldersApiService = new FoldersApiService();
