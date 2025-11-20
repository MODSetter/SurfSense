import { z } from "zod";
import { paginationQueryParams } from ".";

export const documentTypeEnum = z.enum([
	"EXTENSION",
	"CRAWLED_URL",
	"FILE",
	"SLACK_CONNECTOR",
	"NOTION_CONNECTOR",
	"YOUTUBE_VIDEO",
	"GITHUB_CONNECTOR",
	"DISCORD_CONNECTOR",
	"JIRA_CONNECTOR",
	"CONFLUENCE_CONNECTOR",
	"CLICKUP_CONNECTOR",
	"GOOGLE_CALENDAR_CONNECTOR",
	"GOOGLE_GMAIL_CONNECTOR",
	"AIRTABLE_CONNECTOR",
	"LUMA_CONNECTOR",
	"ELASTICSEARCH_CONNECTOR",
	"LINEAR_CONNECTOR",
]);

export const document = z.object({
	id: z.number(),
	title: z.string(),
	document_type: documentTypeEnum,
	document_metadata: z.record(z.string(), z.any()),
	content: z.string(),
	created_at: z.string(),
	search_space_id: z.number(),
});

export const extensionDocumentContent = z.object({
	metadata: z.object({
		BrowsingSessionId: z.string(),
		VisitedWebPageURL: z.string(),
		VisitedWebPageTitle: z.string(),
		VisitedWebPageDateWithTimeInISOString: z.string(),
		VisitedWebPageReffererURL: z.string(),
		VisitedWebPageVisitDurationInMilliseconds: z.string(),
	}),
	pageContent: z.string(),
});

export const documentWithChunks = document.extend({
	chunks: z.array(
		z.object({
			id: z.number(),
			content: z.string(),
			created_at: z.string(),
		})
	),
});

/**
 * Get documents
 */
export const getDocumentsRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			search_space_id: z.number().or(z.string()).optional(),
			document_type: z.array(documentTypeEnum).optional(),
		})
		.nullish(),
});

export const getDocumentsResponse = z.object({
	items: z.array(document),
	total: z.number(),
});

/**
 * Get document
 */
export const getDocumentRequest = document.pick({ id: true });

export const getDocumentResponse = document;

/**
 * Create documents
 */
export const createDocumentRequest = document
	.pick({ document_type: true, search_space_id: true })
	.extend({
		content: z.string().or(z.array(z.string())).or(z.array(extensionDocumentContent)),
	});

export const createDocumentResponse = z.object({
	message: z.literal("Document created successfully"),
});

/**
 * Upload documents
 */
export const uploadDocumentRequest = z.object({
	files: z.array(z.instanceof(File)),
	search_space_id: z.number(),
});

export const uploadDocumentResponse = z.object({
	message: z.literal("Files uploaded for processing"),
});

/**
 * Search documents
 */
export const searchDocumentsRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			search_space_id: z.number().or(z.string()).optional(),
			document_type: z.array(documentTypeEnum).optional(),
			title: z.string().optional(),
		})
		.nullish(),
});

export const searchDocumentsResponse = z.object({
	items: z.array(document),
	total: z.number(),
});

/**
 * Get document type counts
 */
export const getDocumentTypeCountsRequest = z.object({
	queryParams: z
		.object({
			search_space_id: z.number().or(z.string()).optional(),
		})
		.nullish(),
});

export const getDocumentTypeCountsResponse = z.record(z.string(), z.number());

/**
 * Get document by chunk
 */
export const getDocumentByChunkRequest = z.object({
	chunk_id: z.number(),
});

export const getDocumentByChunkResponse = documentWithChunks;

/**
 * Update document
 */
export const updateDocumentRequest = z.object({
	id: z.number(),
	data: document.pick({ search_space_id: true, document_type: true, content: true }),
});

export const updateDocumentResponse = document;

/**
 * Delete document
 */
export const deleteDocumentRequest = document.pick({ id: true });

export const deleteDocumentResponse = z.object({
	message: z.literal("Document deleted successfully"),
});

export type GetDocumentsRequest = z.infer<typeof getDocumentsRequest>;
export type GetDocumentsResponse = z.infer<typeof getDocumentsResponse>;
export type GetDocumentRequest = z.infer<typeof getDocumentRequest>;
export type GetDocumentResponse = z.infer<typeof getDocumentResponse>;
export type CreateDocumentRequest = z.infer<typeof createDocumentRequest>;
export type CreateDocumentResponse = z.infer<typeof createDocumentResponse>;
export type UploadDocumentRequest = z.infer<typeof uploadDocumentRequest>;
export type UploadDocumentResponse = z.infer<typeof uploadDocumentResponse>;
export type SearchDocumentsRequest = z.infer<typeof searchDocumentsRequest>;
export type SearchDocumentsResponse = z.infer<typeof searchDocumentsResponse>;
export type GetDocumentTypeCountsRequest = z.infer<typeof getDocumentTypeCountsRequest>;
export type GetDocumentTypeCountsResponse = z.infer<typeof getDocumentTypeCountsResponse>;
export type GetDocumentByChunkRequest = z.infer<typeof getDocumentByChunkRequest>;
export type GetDocumentByChunkResponse = z.infer<typeof getDocumentByChunkResponse>;
export type UpdateDocumentRequest = z.infer<typeof updateDocumentRequest>;
export type UpdateDocumentResponse = z.infer<typeof updateDocumentResponse>;
export type DeleteDocumentRequest = z.infer<typeof deleteDocumentRequest>;
export type DeleteDocumentResponse = z.infer<typeof deleteDocumentResponse>;
