import type { GetConnectorsRequest } from "@/contracts/types/connector.types";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";
import type { GetLogsRequest } from "@/contracts/types/log.types";
import type { GetSearchSpacesRequest } from "@/contracts/types/search-space.types";

export const cacheKeys = {
	// New chat threads (assistant-ui)
	threads: {
		list: (searchSpaceId: number) => ["threads", searchSpaceId] as const,
		detail: (threadId: number) => ["threads", "detail", threadId] as const,
		search: (searchSpaceId: number, query: string) =>
			["threads", "search", searchSpaceId, query] as const,
	},
	documents: {
		globalQueryParams: (queries: GetDocumentsRequest["queryParams"]) =>
			["documents", ...(queries ? Object.values(queries) : [])] as const,
		withQueryParams: (queries: GetDocumentsRequest["queryParams"]) =>
			["documents-with-queries", ...(queries ? Object.values(queries) : [])] as const,
		document: (documentId: string) => ["document", documentId] as const,
		typeCounts: (searchSpaceId?: string) => ["documents", "type-counts", searchSpaceId] as const,
		byChunk: (chunkId: string) => ["documents", "by-chunk", chunkId] as const,
	},
	logs: {
		list: (searchSpaceId?: number | string) => ["logs", "list", searchSpaceId] as const,
		detail: (logId: number | string) => ["logs", "detail", logId] as const,
		summary: (searchSpaceId?: number | string) => ["logs", "summary", searchSpaceId] as const,
		withQueryParams: (queries: GetLogsRequest["queryParams"]) =>
			["logs", "with-query-params", ...(queries ? Object.values(queries) : [])] as const,
	},
	newLLMConfigs: {
		all: (searchSpaceId: number) => ["new-llm-configs", searchSpaceId] as const,
		byId: (configId: number) => ["new-llm-configs", "detail", configId] as const,
		preferences: (searchSpaceId: number) => ["llm-preferences", searchSpaceId] as const,
		defaultInstructions: () => ["new-llm-configs", "default-instructions"] as const,
		global: () => ["new-llm-configs", "global"] as const,
	},
	auth: {
		user: ["auth", "user"] as const,
	},
	searchSpaces: {
		all: ["search-spaces"] as const,
		withQueryParams: (queries: GetSearchSpacesRequest["queryParams"]) =>
			["search-spaces", ...(queries ? Object.values(queries) : [])] as const,
		detail: (searchSpaceId: string) => ["search-spaces", searchSpaceId] as const,
	},
	user: {
		current: () => ["user", "me"] as const,
	},
	roles: {
		all: (searchSpaceId: string) => ["roles", searchSpaceId] as const,
		byId: (searchSpaceId: string, roleId: string) => ["roles", searchSpaceId, roleId] as const,
	},
	permissions: {
		all: () => ["permissions"] as const,
	},
	members: {
		all: (searchSpaceId: string) => ["members", searchSpaceId] as const,
		myAccess: (searchSpaceId: string) => ["members", "my-access", searchSpaceId] as const,
	},
	invites: {
		all: (searchSpaceId: string) => ["invites", searchSpaceId] as const,
		info: (inviteCode: string) => ["invites", "info", inviteCode] as const,
	},
	connectors: {
		all: (searchSpaceId: string) => ["connectors", searchSpaceId] as const,
		withQueryParams: (queries: GetConnectorsRequest["queryParams"]) =>
			["connectors", ...(queries ? Object.values(queries) : [])] as const,
		byId: (connectorId: string) => ["connector", connectorId] as const,
		index: () => ["connector", "index"] as const,
		googleDrive: {
			folders: (connectorId: number, parentId?: string) =>
				["connectors", "google-drive", connectorId, "folders", parentId] as const,
		},
		composioDrive: {
			folders: (connectorId: number, parentId?: string) =>
				["connectors", "composio-drive", connectorId, "folders", parentId] as const,
		},
	},
	comments: {
		byMessage: (messageId: number) => ["comments", "message", messageId] as const,
	},
	publicChat: {
		byToken: (shareToken: string) => ["public-chat", shareToken] as const,
	},
	publicChatSnapshots: {
		all: ["public-chat-snapshots"] as const,
		bySearchSpace: (searchSpaceId: number) =>
			["public-chat-snapshots", "search-space", searchSpaceId] as const,
	},
};
