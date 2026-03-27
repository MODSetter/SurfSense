import { z } from "zod";

export const folder = z.object({
	id: z.number(),
	name: z.string(),
	position: z.string(),
	parent_id: z.number().nullable(),
	search_space_id: z.number(),
	created_by_id: z.string().nullable().optional(),
	created_at: z.string(),
	updated_at: z.string(),
});

export const folderCreateRequest = z.object({
	name: z.string().min(1).max(255),
	parent_id: z.number().nullable().optional(),
	search_space_id: z.number(),
});

export const folderUpdateRequest = z.object({
	name: z.string().min(1).max(255),
});

export const folderMoveRequest = z.object({
	new_parent_id: z.number().nullable().optional(),
});

export const folderReorderRequest = z.object({
	before_position: z.string().nullable().optional(),
	after_position: z.string().nullable().optional(),
});

export const folderBreadcrumb = z.object({
	id: z.number(),
	name: z.string(),
});

export const documentMoveRequest = z.object({
	folder_id: z.number().nullable().optional(),
});

export const bulkDocumentMoveRequest = z.object({
	document_ids: z.array(z.number()),
	folder_id: z.number().nullable().optional(),
});

export const folderListResponse = z.array(folder);
export const folderBreadcrumbResponse = z.array(folderBreadcrumb);

export const folderDeleteResponse = z.object({
	message: z.string(),
	documents_queued_for_deletion: z.number(),
});

export type Folder = z.infer<typeof folder>;
export type FolderCreateRequest = z.infer<typeof folderCreateRequest>;
export type FolderUpdateRequest = z.infer<typeof folderUpdateRequest>;
export type FolderMoveRequest = z.infer<typeof folderMoveRequest>;
export type FolderReorderRequest = z.infer<typeof folderReorderRequest>;
export type FolderBreadcrumb = z.infer<typeof folderBreadcrumb>;
export type DocumentMoveRequest = z.infer<typeof documentMoveRequest>;
export type BulkDocumentMoveRequest = z.infer<typeof bulkDocumentMoveRequest>;
export type FolderListResponse = z.infer<typeof folderListResponse>;
export type FolderBreadcrumbResponse = z.infer<typeof folderBreadcrumbResponse>;
export type FolderDeleteResponse = z.infer<typeof folderDeleteResponse>;
