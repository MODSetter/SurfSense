import type { GetConnectorsRequest } from "@/contracts/types/connector.types";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";
import type { GetLogsRequest } from "@/contracts/types/log.types";
import type { GetSearchSpacesRequest } from "@/contracts/types/search-space.types";

/**
 * Convert an object to a stable array of [key, value] pairs sorted by key.
 * This ensures cache keys are order-independent (avoiding Object.values order-dependency).
 * Filters out undefined values.
 */
function stableEntries(obj: Record<string, unknown> | null | undefined): unknown[] {
	if (!obj) return [];
	return Object.entries(obj)
		.filter(([, v]) => v !== undefined)
		.sort(([a], [b]) => a.localeCompare(b))
		.flat();
}

export const cacheKeys = {
	// New chat threads (assistant-ui)
	threads: {
		detail: (threadId: number) => ["threads", "detail", threadId] as const,
		messages: (threadId: number) => ["threads", "messages", threadId] as const,
	},
	documents: {
		globalQueryParams: (queries: GetDocumentsRequest["queryParams"]) =>
			["documents", ...stableEntries(queries)] as const,
		withQueryParams: (queries: GetDocumentsRequest["queryParams"]) =>
			["documents-with-queries", ...stableEntries(queries)] as const,
		document: (documentId: string) => ["document", documentId] as const,
	},
	logs: {
		list: (searchSpaceId?: number | string) => ["logs", "list", searchSpaceId] as const,
		detail: (logId: number | string) => ["logs", "detail", logId] as const,
		summary: (searchSpaceId?: number | string) => ["logs", "summary", searchSpaceId] as const,
		withQueryParams: (queries: GetLogsRequest["queryParams"]) =>
			["logs", "with-query-params", ...stableEntries(queries)] as const,
	},
	modelConnections: {
		all: (searchSpaceId: number) => ["model-connections", searchSpaceId] as const,
		global: () => ["model-connections", "global"] as const,
		globalConfigStatus: () => ["model-connections", "global-config-status"] as const,
		providers: () => ["model-connections", "providers"] as const,
		roles: (searchSpaceId: number) => ["model-roles", searchSpaceId] as const,
	},
	auth: {
		user: ["auth", "user"] as const,
	},
	searchSpaces: {
		all: ["search-spaces"] as const,
		withQueryParams: (queries: GetSearchSpacesRequest["queryParams"]) =>
			["search-spaces", ...stableEntries(queries)] as const,
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
	agentTools: {
		all: () => ["agent-tools"] as const,
	},
	connectors: {
		all: (searchSpaceId: string) => ["connectors", searchSpaceId] as const,
		withQueryParams: (queries: GetConnectorsRequest["queryParams"]) =>
			["connectors", ...stableEntries(queries)] as const,
		byId: (connectorId: string) => ["connector", connectorId] as const,
		index: () => ["connector", "index"] as const,
		googleDrive: {
			folders: (connectorId: number, parentId?: string) =>
				["connectors", "google-drive", connectorId, "folders", parentId] as const,
		},
	},
	comments: {
		byMessage: (messageId: number) => ["comments", "message", messageId] as const,
	},
	publicChat: {
		byToken: (shareToken: string) => ["public-chat", shareToken] as const,
	},
	github: {
		repoStars: (username: string, repo: string) =>
			["github", "repo-stars", username, repo] as const,
	},
	publicChatSnapshots: {
		all: ["public-chat-snapshots"] as const,
		bySearchSpace: (searchSpaceId: number) =>
			["public-chat-snapshots", "search-space", searchSpaceId] as const,
	},
	prompts: {
		all: () => ["prompts"] as const,
		public: () => ["prompts", "public"] as const,
	},
	notifications: {
		search: (searchSpaceId: number | null, search: string, tab: string) =>
			["notifications", "search", searchSpaceId, search, tab] as const,
		sourceTypes: (searchSpaceId: number | null) =>
			["notifications", "source-types", searchSpaceId] as const,
		batchUnreadCounts: (searchSpaceId: number | null) =>
			["notifications", "unread-counts-batch", searchSpaceId] as const,
	},
	automations: {
		// list endpoint is keyed by pagination too so distinct pages don't collide
		list: (searchSpaceId: number, limit: number, offset: number) =>
			["automations", "list", searchSpaceId, limit, offset] as const,
		detail: (automationId: number) => ["automations", "detail", automationId] as const,
		runs: (automationId: number, limit: number, offset: number) =>
			["automations", "runs", automationId, limit, offset] as const,
		run: (automationId: number, runId: number) =>
			["automations", "runs", automationId, runId] as const,
		modelEligibility: (searchSpaceId: number) =>
			["automations", "model-eligibility", searchSpaceId] as const,
	},
};
