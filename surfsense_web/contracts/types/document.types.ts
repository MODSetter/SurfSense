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
	"LINEAR_CONNECTOR",
	"DISCORD_CONNECTOR",
	"JIRA_CONNECTOR",
	"CONFLUENCE_CONNECTOR",
	"CLICKUP_CONNECTOR",
	"GOOGLE_CALENDAR_CONNECTOR",
	"GOOGLE_GMAIL_CONNECTOR",
	"AIRTABLE_CONNECTOR",
	"LUMA_CONNECTOR",
	"ELASTICSEARCH_CONNECTOR",
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

export const getDocumentsRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			search_space_id: z.number().or(z.string()).optional(),
			document_type: z.array(documentTypeEnum).optional(),
		})
		.nullish(),
});

export const getDocumentResponse = z.object({
	items: z.array(document),
	total: z.number(),
});

export const createDocumentRequest = document
	.pick({ document_type: true, search_space_id: true })
	.extend({
		content: z.string().or(z.array(z.string())).or(z.array(extensionDocumentContent)),
	});

export const createDocumentResponse = z.object({
	message: z.literal("Document created successfully"),
});

export type GetDocumentsRequest = z.infer<typeof getDocumentsRequest>;
export type GetDocumentResponse = z.infer<typeof getDocumentResponse>;
export type CreateDocumentRequest = z.infer<typeof createDocumentRequest>;
export type CreateDocumentResponse = z.infer<typeof createDocumentResponse>;
