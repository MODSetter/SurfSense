import type { GetConnectorsRequest } from "@/contracts/types/connector.types";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";
import type { GetLogsRequest } from "@/contracts/types/log.types";
import type { GetWorkspacesRequest } from "@/contracts/types/workspace.types";

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
		list: (workspaceId?: number | string) => ["logs", "list", workspaceId] as const,
		detail: (logId: number | string) => ["logs", "detail", logId] as const,
		summary: (workspaceId?: number | string) => ["logs", "summary", workspaceId] as const,
		withQueryParams: (queries: GetLogsRequest["queryParams"]) =>
			["logs", "with-query-params", ...stableEntries(queries)] as const,
	},
	modelConnections: {
		all: (workspaceId: number) => ["model-connections", workspaceId] as const,
		global: () => ["model-connections", "global"] as const,
		globalConfigStatus: () => ["model-connections", "global-config-status"] as const,
		providers: () => ["model-connections", "providers"] as const,
		roles: (workspaceId: number) => ["model-roles", workspaceId] as const,
		setupStatus: (workspaceId: number) => ["llm-setup-status", workspaceId] as const,
	},
	auth: {
		user: ["auth", "user"] as const,
	},
	workspaces: {
		all: ["workspaces"] as const,
		withQueryParams: (queries: GetWorkspacesRequest["queryParams"]) =>
			["workspaces", ...stableEntries(queries)] as const,
		detail: (workspaceId: string) => ["workspaces", workspaceId] as const,
	},
	user: {
		current: () => ["user", "me"] as const,
	},
	roles: {
		all: (workspaceId: string) => ["roles", workspaceId] as const,
		byId: (workspaceId: string, roleId: string) => ["roles", workspaceId, roleId] as const,
	},
	permissions: {
		all: () => ["permissions"] as const,
	},
	members: {
		all: (workspaceId: string) => ["members", workspaceId] as const,
		myAccess: (workspaceId: string) => ["members", "my-access", workspaceId] as const,
	},
	invites: {
		all: (workspaceId: string) => ["invites", workspaceId] as const,
		info: (inviteCode: string) => ["invites", "info", inviteCode] as const,
	},
	agentTools: {
		all: () => ["agent-tools"] as const,
	},
	connectors: {
		all: (workspaceId: string) => ["connectors", workspaceId] as const,
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
		byWorkspace: (workspaceId: number) =>
			["public-chat-snapshots", "workspace", workspaceId] as const,
	},
	prompts: {
		all: () => ["prompts"] as const,
		public: () => ["prompts", "public"] as const,
	},
	notifications: {
		search: (workspaceId: number | null, search: string, tab: string) =>
			["notifications", "search", workspaceId, search, tab] as const,
		sourceTypes: (workspaceId: number | null) =>
			["notifications", "source-types", workspaceId] as const,
		batchUnreadCounts: (workspaceId: number | null) =>
			["notifications", "unread-counts-batch", workspaceId] as const,
	},
	scrapers: {
		capabilities: (workspaceId: number | string) =>
			["scrapers", "capabilities", workspaceId] as const,
		runs: (workspaceId: number | string) => ["scrapers", "runs", workspaceId] as const,
		run: (workspaceId: number | string, runId: string) =>
			["scrapers", "run", workspaceId, runId] as const,
	},
	automations: {
		// list endpoint is keyed by pagination too so distinct pages don't collide
		list: (workspaceId: number, limit: number, offset: number) =>
			["automations", "list", workspaceId, limit, offset] as const,
		detail: (automationId: number) => ["automations", "detail", automationId] as const,
		runs: (automationId: number, limit: number, offset: number) =>
			["automations", "runs", automationId, limit, offset] as const,
		run: (automationId: number, runId: number) =>
			["automations", "runs", automationId, runId] as const,
		modelEligibility: (workspaceId: number) =>
			["automations", "model-eligibility", workspaceId] as const,
	},
};
