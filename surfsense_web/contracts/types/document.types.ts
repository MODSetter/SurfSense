import { z } from "zod";
import { paginationQueryParams } from ".";

export const documentTypeEnum = z.enum([
	"EXTENSION",
	"CRAWLED_URL",
	"FILE",
	"SLACK_CONNECTOR",
	"TEAMS_CONNECTOR",
	"NOTION_CONNECTOR",
	"YOUTUBE_VIDEO",
	"GITHUB_CONNECTOR",
	"LINEAR_CONNECTOR",
	"DISCORD_CONNECTOR",
	"JIRA_CONNECTOR",
	"CONFLUENCE_CONNECTOR",
	"CLICKUP_CONNECTOR",
	"GOOGLE_CALENDAR_CONNECTOR",
	"GOOGLE_GMAIL_CONNECTOR",
	"GOOGLE_DRIVE_FILE",
	"AIRTABLE_CONNECTOR",
	"LUMA_CONNECTOR",
	"ELASTICSEARCH_CONNECTOR",
	"BOOKSTACK_CONNECTOR",
	"CIRCLEBACK",
	"SURFSENSE_DOCS",
	"NOTE",
	"COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
	"COMPOSIO_GMAIL_CONNECTOR",
	"COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
]);

export const document = z.object({
	id: z.number(),
	title: z.string(),
	document_type: documentTypeEnum,
	document_metadata: z.record(z.string(), z.any()),
	content: z.string(),
	content_hash: z.string(),
	unique_identifier_hash: z.string().nullable(),
	created_at: z.string(),
	updated_at: z.string().nullable(),
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
 * Surfsense documentation schemas
 * Follows the same pattern as document/documentWithChunks
 */
export const surfsenseDocsChunk = z.object({
	id: z.number(),
	content: z.string(),
});

export const surfsenseDocsDocument = z.object({
	id: z.number(),
	title: z.string(),
	source: z.string(),
	content: z.string(),
});

export const surfsenseDocsDocumentWithChunks = surfsenseDocsDocument.extend({
	chunks: z.array(surfsenseDocsChunk),
});

/**
 * Get documents
 */
export const getDocumentsRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			search_space_id: z.number().or(z.string()).optional(),
			document_types: z.array(documentTypeEnum).optional(),
		})
		.nullish(),
});

export const getDocumentsResponse = z.object({
	items: z.array(document),
	total: z.number(),
	page: z.number(),
	page_size: z.number(),
	has_more: z.boolean(),
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
	message: z.literal("Documents created successfully"),
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
			document_types: z.array(documentTypeEnum).optional(),
			title: z.string().optional(),
		})
		.nullish(),
});

export const searchDocumentsResponse = z.object({
	items: z.array(document),
	total: z.number(),
	page: z.number(),
	page_size: z.number(),
	has_more: z.boolean(),
});

/**
 * Search document titles (lightweight, for mention picker)
 */
export const documentTitleRead = z.object({
	id: z.number(),
	title: z.string(),
	document_type: documentTypeEnum,
});

export const searchDocumentTitlesRequest = z.object({
	queryParams: z.object({
		search_space_id: z.number(),
		title: z.string().optional(),
		page: z.number().optional(),
		page_size: z.number().optional(),
	}),
});

export const searchDocumentTitlesResponse = z.object({
	items: z.array(documentTitleRead),
	has_more: z.boolean(),
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
 * Get Surfsense docs by chunk
 */
export const getSurfsenseDocsByChunkRequest = z.object({
	chunk_id: z.number(),
});

export const getSurfsenseDocsByChunkResponse = surfsenseDocsDocumentWithChunks;

/**
 * List Surfsense docs
 */
export const getSurfsenseDocsRequest = z.object({
	queryParams: paginationQueryParams.extend({
		title: z.string().optional(),
	}),
});

export const getSurfsenseDocsResponse = z.object({
	items: z.array(surfsenseDocsDocument),
	total: z.number(),
	page: z.number(),
	page_size: z.number(),
	has_more: z.boolean(),
});

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

export type Document = z.infer<typeof document>;
export type DocumentTitleRead = z.infer<typeof documentTitleRead>;
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
export type SearchDocumentTitlesRequest = z.infer<typeof searchDocumentTitlesRequest>;
export type SearchDocumentTitlesResponse = z.infer<typeof searchDocumentTitlesResponse>;
export type GetDocumentTypeCountsRequest = z.infer<typeof getDocumentTypeCountsRequest>;
export type GetDocumentTypeCountsResponse = z.infer<typeof getDocumentTypeCountsResponse>;
export type GetDocumentByChunkRequest = z.infer<typeof getDocumentByChunkRequest>;
export type GetDocumentByChunkResponse = z.infer<typeof getDocumentByChunkResponse>;
export type UpdateDocumentRequest = z.infer<typeof updateDocumentRequest>;
export type UpdateDocumentResponse = z.infer<typeof updateDocumentResponse>;
export type DeleteDocumentRequest = z.infer<typeof deleteDocumentRequest>;
export type DeleteDocumentResponse = z.infer<typeof deleteDocumentResponse>;
export type DocumentTypeEnum = z.infer<typeof documentTypeEnum>;
export type SurfsenseDocsChunk = z.infer<typeof surfsenseDocsChunk>;
export type SurfsenseDocsDocument = z.infer<typeof surfsenseDocsDocument>;
export type SurfsenseDocsDocumentWithChunks = z.infer<typeof surfsenseDocsDocumentWithChunks>;
export type GetSurfsenseDocsByChunkRequest = z.infer<typeof getSurfsenseDocsByChunkRequest>;
export type GetSurfsenseDocsByChunkResponse = z.infer<typeof getSurfsenseDocsByChunkResponse>;
export type GetSurfsenseDocsRequest = z.infer<typeof getSurfsenseDocsRequest>;
export type GetSurfsenseDocsResponse = z.infer<typeof getSurfsenseDocsResponse>;
