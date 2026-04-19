/**
 * Shared types for the SurfSense Obsidian plugin.
 *
 * Kept in a leaf module with no other src/ imports so it can be imported
 * from anywhere (settings, api-client, sync-engine, status-bar, main)
 * without creating cycles.
 */

export interface SurfsensePluginSettings {
	serverUrl: string;
	apiToken: string;
	searchSpaceId: number | null;
	connectorId: number | null;
	vaultId: string;
	vaultName: string;
	deviceId: string;
	deviceLabel: string;
	syncMode: "auto" | "manual";
	excludePatterns: string[];
	includeAttachments: boolean;
	lastSyncAt: number | null;
	lastReconcileAt: number | null;
	filesSynced: number;
	queue: QueueItem[];
	tombstones: Record<string, number>;
}

export const DEFAULT_SETTINGS: SurfsensePluginSettings = {
	serverUrl: "https://api.surfsense.com",
	apiToken: "",
	searchSpaceId: null,
	connectorId: null,
	vaultId: "",
	vaultName: "",
	deviceId: "",
	deviceLabel: "",
	syncMode: "auto",
	excludePatterns: [".trash", "_attachments", "templates"],
	includeAttachments: false,
	lastSyncAt: null,
	lastReconcileAt: null,
	filesSynced: 0,
	queue: [],
	tombstones: {},
};

export type QueueOp = "upsert" | "delete" | "rename";

export interface UpsertItem {
	op: "upsert";
	path: string;
	enqueuedAt: number;
	attempt: number;
}

export interface DeleteItem {
	op: "delete";
	path: string;
	enqueuedAt: number;
	attempt: number;
}

export interface RenameItem {
	op: "rename";
	oldPath: string;
	newPath: string;
	enqueuedAt: number;
	attempt: number;
}

export type QueueItem = UpsertItem | DeleteItem | RenameItem;

export interface NotePayload {
	vault_id: string;
	path: string;
	name: string;
	extension: string;
	content: string;
	frontmatter: Record<string, unknown>;
	tags: string[];
	headings: HeadingRef[];
	resolved_links: string[];
	unresolved_links: string[];
	embeds: string[];
	aliases: string[];
	content_hash: string;
	mtime: number;
	ctime: number;
	[key: string]: unknown;
}

export interface HeadingRef {
	heading: string;
	level: number;
}

export interface SearchSpace {
	id: number;
	name: string;
	description?: string;
	[key: string]: unknown;
}

export interface ConnectResponse {
	connector_id: number;
	vault_id: string;
	search_space_id: number;
	api_version: string;
	capabilities: string[];
	server_time_utc: string;
	[key: string]: unknown;
}

export interface HealthResponse {
	api_version: string;
	capabilities: string[];
	server_time_utc: string;
	[key: string]: unknown;
}

export interface ManifestEntry {
	hash: string;
	mtime: number;
	[key: string]: unknown;
}

export interface ManifestResponse {
	vault_id: string;
	entries: Record<string, ManifestEntry>;
	[key: string]: unknown;
}

export type StatusKind =
	| "idle"
	| "syncing"
	| "queued"
	| "offline"
	| "auth-error"
	| "error";

export interface StatusState {
	kind: StatusKind;
	detail?: string;
	queueDepth: number;
}
