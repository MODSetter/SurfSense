/** Shared types for the SurfSense Obsidian plugin. Leaf module — no src/ imports. */

export interface SurfsensePluginSettings {
	serverUrl: string;
	apiToken: string;
	searchSpaceId: number | null;
	connectorId: number | null;
	/** UUID for the vault — lives here so Obsidian Sync replicates it across devices. */
	vaultId: string;
	/** 0 disables periodic reconcile (Force sync still works). */
	syncIntervalMinutes: number;
	/** Mobile-only: pause auto-sync when on cellular. iOS can't detect network type, so the toggle is a no-op there. */
	wifiOnly: boolean;
	includeFolders: string[];
	excludeFolders: string[];
	excludePatterns: string[];
	includeAttachments: boolean;
	lastSyncAt: number | null;
	lastReconcileAt: number | null;
	filesSynced: number;
	queue: QueueItem[];
	tombstones: Record<string, number>;
}

export const DEFAULT_SETTINGS: SurfsensePluginSettings = {
	serverUrl: "https://surfsense.com",
	apiToken: "",
	searchSpaceId: null,
	connectorId: null,
	vaultId: "",
	syncIntervalMinutes: 10,
	wifiOnly: false,
	includeFolders: [],
	excludeFolders: [],
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
	/** Byte size of the local file; pairs with mtime for the reconcile short-circuit. */
	size: number;
	mtime: number;
	ctime: number;
	/** Non-markdown attachment marker; enables backend ETL path. */
	is_binary?: boolean;
	/** Base64-encoded file bytes for binary attachments. */
	binary_base64?: string;
	/** Optional MIME type hint for backend parsers. */
	mime_type?: string;
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
	capabilities: string[];
	server_time_utc: string;
	[key: string]: unknown;
}

export interface HealthResponse {
	capabilities: string[];
	server_time_utc: string;
	[key: string]: unknown;
}

export interface ManifestEntry {
	hash: string;
	mtime: number;
	/** Optional: byte size of stored content. Enables mtime+size short-circuit; falls back to upsert when missing. */
	size?: number;
	[key: string]: unknown;
}

export interface ManifestResponse {
	vault_id: string;
	items: Record<string, ManifestEntry>;
	[key: string]: unknown;
}

/** Per-item ack shapes — mirror `app/schemas/obsidian_plugin.py` 1:1. */
export interface SyncAckItem {
	path: string;
	status: "ok" | "error";
	document_id?: number;
	error?: string;
}

export interface SyncAck {
	vault_id: string;
	indexed: number;
	failed: number;
	items: SyncAckItem[];
}

export interface RenameAckItem {
	old_path: string;
	new_path: string;
	status: "ok" | "error" | "missing";
	document_id?: number;
	error?: string;
}

export interface RenameAck {
	vault_id: string;
	renamed: number;
	missing: number;
	items: RenameAckItem[];
}

export interface DeleteAckItem {
	path: string;
	status: "ok" | "error" | "missing";
	error?: string;
}

export interface DeleteAck {
	vault_id: string;
	deleted: number;
	missing: number;
	items: DeleteAckItem[];
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
