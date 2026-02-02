import { z } from "zod";
import { paginationQueryParams } from ".";

export const searchSourceConnectorTypeEnum = z.enum([
	"SERPER_API",
	"TAVILY_API",
	"SEARXNG_API",
	"LINKUP_API",
	"BAIDU_SEARCH_API",
	"SLACK_CONNECTOR",
	"TEAMS_CONNECTOR",
	"NOTION_CONNECTOR",
	"GITHUB_CONNECTOR",
	"LINEAR_CONNECTOR",
	"DISCORD_CONNECTOR",
	"JIRA_CONNECTOR",
	"CONFLUENCE_CONNECTOR",
	"CLICKUP_CONNECTOR",
	"GOOGLE_CALENDAR_CONNECTOR",
	"GOOGLE_GMAIL_CONNECTOR",
	"GOOGLE_DRIVE_CONNECTOR",
	"AIRTABLE_CONNECTOR",
	"LUMA_CONNECTOR",
	"ELASTICSEARCH_CONNECTOR",
	"WEBCRAWLER_CONNECTOR",
	"YOUTUBE_CONNECTOR",
	"BOOKSTACK_CONNECTOR",
	"CIRCLEBACK_CONNECTOR",
	"MCP_CONNECTOR",
	"OBSIDIAN_CONNECTOR",
	"COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
	"COMPOSIO_GMAIL_CONNECTOR",
	"COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
]);

export const searchSourceConnector = z.object({
	id: z.number(),
	name: z.string(),
	connector_type: searchSourceConnectorTypeEnum,
	is_indexable: z.boolean(),
	is_active: z.boolean().default(true),
	last_indexed_at: z.string().nullable(),
	config: z.record(z.string(), z.any()),
	periodic_indexing_enabled: z.boolean(),
	indexing_frequency_minutes: z.number().nullable(),
	next_scheduled_at: z.string().nullable(),
	search_space_id: z.number(),
	user_id: z.string(),
	created_at: z.string(),
});

export const googleDriveItem = z.object({
	id: z.string(),
	name: z.string(),
	mimeType: z.string(),
	isFolder: z.boolean(),
	parents: z.array(z.string()).optional(),
	size: z.coerce.number().optional(),
	iconLink: z.string().optional(),
	webViewLink: z.string().optional(),
	createdTime: z.string().optional(),
	modifiedTime: z.string().optional(),
});

/**
 * Get connectors
 */
export const getConnectorsRequest = z.object({
	queryParams: paginationQueryParams
		.pick({ skip: true, limit: true })
		.extend({
			search_space_id: z.number().or(z.string()).nullish(),
		})
		.nullish(),
});

export const getConnectorsResponse = z.array(searchSourceConnector);

/**
 * Get connector
 */
export const getConnectorRequest = searchSourceConnector.pick({ id: true });

export const getConnectorResponse = searchSourceConnector;

/**
 * Create connector
 */
export const createConnectorRequest = z.object({
	data: searchSourceConnector.pick({
		name: true,
		connector_type: true,
		is_indexable: true,
		is_active: true,
		last_indexed_at: true,
		config: true,
		periodic_indexing_enabled: true,
		indexing_frequency_minutes: true,
		next_scheduled_at: true,
	}),
	queryParams: z.object({
		search_space_id: z.number().or(z.string()),
	}),
});

export const createConnectorResponse = searchSourceConnector;

/**
 * Update connector
 */
export const updateConnectorRequest = z.object({
	id: z.number(),
	data: searchSourceConnector
		.pick({
			name: true,
			connector_type: true,
			is_indexable: true,
			is_active: true,
			last_indexed_at: true,
			config: true,
			periodic_indexing_enabled: true,
			indexing_frequency_minutes: true,
			next_scheduled_at: true,
		})
		.partial(),
});

export const updateConnectorResponse = searchSourceConnector;

/**
 * Delete connector
 */
export const deleteConnectorRequest = searchSourceConnector.pick({ id: true });

export const deleteConnectorResponse = z.object({
	message: z.literal("Search source connector deleted successfully"),
});

/**
 * Google Drive index request body
 */
export const googleDriveIndexBody = z.object({
	folders: z.array(
		z.object({
			id: z.string(),
			name: z.string(),
		})
	),
	files: z.array(
		z.object({
			id: z.string(),
			name: z.string(),
		})
	),
	indexing_options: z
		.object({
			max_files_per_folder: z.number().int().min(1).max(1000),
			incremental_sync: z.boolean(),
			include_subfolders: z.boolean(),
		})
		.optional(),
});

/**
 * Index connector
 */
export const indexConnectorRequest = z.object({
	connector_id: z.number(),
	queryParams: z.object({
		search_space_id: z.number().or(z.string()),
		start_date: z.string().optional(),
		end_date: z.string().optional(),
	}),
	body: googleDriveIndexBody.optional(),
});

export const indexConnectorResponse = z.object({
	message: z.string(),
	connector_id: z.number(),
	search_space_id: z.number(),
	indexing_from: z.string(),
	indexing_to: z.string(),
});

/**
 * List GitHub repositories
 */
export const listGitHubRepositoriesRequest = z.object({
	github_pat: z.string(),
});

export const listGitHubRepositoriesResponse = z.array(z.record(z.string(), z.any()));

/**
 * List Google Drive folders
 */
export const listGoogleDriveFoldersRequest = z.object({
	connector_id: z.number(),
	parent_id: z.string().optional(),
});

export const listGoogleDriveFoldersResponse = z.object({
	items: z.array(googleDriveItem),
});

/**
 * Slack channel with bot membership status
 */
export const slackChannel = z.object({
	id: z.string(),
	name: z.string(),
	is_private: z.boolean(),
	is_member: z.boolean(),
});

/**
 * List Slack channels
 */
export const listSlackChannelsRequest = z.object({
	connector_id: z.number(),
});

export const listSlackChannelsResponse = z.array(slackChannel);

/**
 * Discord channel with indexing permission info
 */
export const discordChannel = z.object({
	id: z.string(),
	name: z.string(),
	type: z.enum(["text", "announcement"]),
	position: z.number(),
	category_id: z.string().nullable().optional(),
	can_index: z.boolean(),
});

/**
 * List Discord channels
 */
export const listDiscordChannelsRequest = z.object({
	connector_id: z.number(),
});

export const listDiscordChannelsResponse = z.array(discordChannel);

// Inferred types
export type SearchSourceConnectorType = z.infer<typeof searchSourceConnectorTypeEnum>;
export type SearchSourceConnector = z.infer<typeof searchSourceConnector>;
export type GetConnectorsRequest = z.infer<typeof getConnectorsRequest>;
export type GetConnectorsResponse = z.infer<typeof getConnectorsResponse>;
export type GetConnectorRequest = z.infer<typeof getConnectorRequest>;
export type GetConnectorResponse = z.infer<typeof getConnectorResponse>;
export type CreateConnectorRequest = z.infer<typeof createConnectorRequest>;
export type CreateConnectorResponse = z.infer<typeof createConnectorResponse>;
export type UpdateConnectorRequest = z.infer<typeof updateConnectorRequest>;
export type UpdateConnectorResponse = z.infer<typeof updateConnectorResponse>;
export type DeleteConnectorRequest = z.infer<typeof deleteConnectorRequest>;
export type DeleteConnectorResponse = z.infer<typeof deleteConnectorResponse>;
export type IndexConnectorRequest = z.infer<typeof indexConnectorRequest>;
export type IndexConnectorResponse = z.infer<typeof indexConnectorResponse>;
export type ListGitHubRepositoriesRequest = z.infer<typeof listGitHubRepositoriesRequest>;
export type ListGitHubRepositoriesResponse = z.infer<typeof listGitHubRepositoriesResponse>;
export type ListGoogleDriveFoldersRequest = z.infer<typeof listGoogleDriveFoldersRequest>;
export type ListGoogleDriveFoldersResponse = z.infer<typeof listGoogleDriveFoldersResponse>;
export type GoogleDriveItem = z.infer<typeof googleDriveItem>;
export type SlackChannel = z.infer<typeof slackChannel>;
export type ListSlackChannelsRequest = z.infer<typeof listSlackChannelsRequest>;
export type ListSlackChannelsResponse = z.infer<typeof listSlackChannelsResponse>;
export type DiscordChannel = z.infer<typeof discordChannel>;
export type ListDiscordChannelsRequest = z.infer<typeof listDiscordChannelsRequest>;
export type ListDiscordChannelsResponse = z.infer<typeof listDiscordChannelsResponse>;
