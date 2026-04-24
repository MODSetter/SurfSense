import {
	type App,
	type CachedMetadata,
	type Debouncer,
	Notice,
	type TAbstractFile,
	TFile,
	debounce,
} from "obsidian";
import {
	AuthError,
	PermanentError,
	type SurfSenseApiClient,
	TransientError,
	VaultNotRegisteredError,
} from "./api-client";
import { isExcluded, isFolderFiltered } from "./excludes";
import { buildNotePayload } from "./payload";
import { type BatchResult, PersistentQueue } from "./queue";
import type {
	HealthResponse,
	ManifestEntry,
	NotePayload,
	QueueItem,
	StatusKind,
	StatusState,
} from "./types";
import { computeVaultFingerprint } from "./vault-identity";

/**
 * Reconciles vault state with the server.
 * Start order: connect (or /health) → drain queue → reconcile → subscribe events.
 */

export interface SyncEngineDeps {
	app: App;
	apiClient: SurfSenseApiClient;
	queue: PersistentQueue;
	getSettings: () => SyncEngineSettings;
	saveSettings: (mut: (s: SyncEngineSettings) => void) => Promise<void>;
	setStatus: (s: StatusState) => void;
	onCapabilities: (caps: string[]) => void;
	/** Fired when the adaptive backoff multiplier may have changed; main.ts uses it to reschedule. */
	onReconcileBackoffChanged?: () => void;
}

export interface SyncEngineSettings {
	vaultId: string;
	connectorId: number | null;
	searchSpaceId: number | null;
	includeFolders: string[];
	excludeFolders: string[];
	excludePatterns: string[];
	includeAttachments: boolean;
	lastReconcileAt: number | null;
	lastSyncAt: number | null;
	filesSynced: number;
	tombstones: Record<string, number>;
}

export const RECONCILE_MIN_INTERVAL_MS = 5 * 60 * 1000;
const TOMBSTONE_TTL_MS = 24 * 60 * 60 * 1000; // 1 day
const PENDING_DEBOUNCE_MS = 1500;

export class SyncEngine {
	private readonly deps: SyncEngineDeps;
	private capabilities: string[] = [];
	private pendingMdEdits = new Map<string, Debouncer<[], void>>();
	/** Consecutive reconciles that found no work; powers the adaptive interval. */
	private idleReconcileStreak = 0;
	/** 2^streak is capped at this value (e.g. 8 → max ×8 backoff). */
	private readonly maxBackoffMultiplier = 8;

	constructor(deps: SyncEngineDeps) {
		this.deps = deps;
	}

	/** Returns the next-tick interval given the user's base, scaled by the idle streak. */
	getReconcileBackoffMs(baseMs: number): number {
		const multiplier = Math.min(2 ** this.idleReconcileStreak, this.maxBackoffMultiplier);
		return baseMs * multiplier;
	}

	getCapabilities(): readonly string[] {
		return this.capabilities;
	}

	supports(capability: string): boolean {
		return this.capabilities.includes(capability);
	}

	/** Run the onload sequence described in this file's docstring. */
	async start(): Promise<void> {
		this.setStatus("syncing", "Connecting to SurfSense…");

		const settings = this.deps.getSettings();
		if (!settings.searchSpaceId) {
			// No target yet — /health still surfaces auth/network errors.
			try {
				const health = await this.deps.apiClient.health();
				this.applyHealth(health);
			} catch (err) {
				this.handleStartupError(err);
				return;
			}
			this.setStatus("idle", "Pick a search space in settings to start syncing.");
			return;
		}

		// Re-announce so the backend sees the latest vault_name + last_connect_at.
		// flushQueue gates on connectorId, so a failed connect leaves the queue intact.
		await this.ensureConnected();

		await this.flushQueue();
		await this.maybeReconcile();
		this.setStatus(this.queueStatusKind(), undefined);
	}

	/**
	 * (Re)register the vault. Adopts server's `vault_id` in case fingerprint
	 * dedup routed us to an existing row from another device.
	 */
	async ensureConnected(): Promise<boolean> {
		const settings = this.deps.getSettings();
		if (!settings.searchSpaceId) {
			this.setStatus("idle", "Pick a search space in settings.");
			return false;
		}
		this.setStatus("syncing", "Connecting to SurfSense");
		try {
			const fingerprint = await computeVaultFingerprint(this.deps.app);
			const resp = await this.deps.apiClient.connect({
				searchSpaceId: settings.searchSpaceId,
				vaultId: settings.vaultId,
				vaultName: this.deps.app.vault.getName(),
				vaultFingerprint: fingerprint,
			});
			this.applyHealth(resp);
			await this.deps.saveSettings((s) => {
				s.vaultId = resp.vault_id;
				s.connectorId = resp.connector_id;
			});
			this.setStatus(this.queueStatusKind(), this.statusDetail());
			return true;
		} catch (err) {
			this.handleStartupError(err);
			return false;
		}
	}

	applyHealth(h: HealthResponse): void {
		this.capabilities = Array.isArray(h.capabilities) ? [...h.capabilities] : [];
		this.deps.onCapabilities(this.capabilities);
	}

	// ---- vault event handlers --------------------------------------------

	onCreate(file: TAbstractFile): void {
		if (!this.shouldTrack(file)) return;
		const settings = this.deps.getSettings();
		if (this.isExcluded(file.path, settings)) return;
		this.resetIdleStreak();
		if (this.isMarkdown(file)) {
			this.scheduleMdUpsert(file.path);
			return;
		}
		this.deps.queue.enqueueUpsert(file.path);
	}

	onModify(file: TAbstractFile): void {
		if (!this.shouldTrack(file)) return;
		const settings = this.deps.getSettings();
		if (this.isExcluded(file.path, settings)) return;
		this.resetIdleStreak();
		if (this.isMarkdown(file)) {
			// Wait for metadataCache.changed so the payload sees fresh metadata.
			this.scheduleMdUpsert(file.path);
			return;
		}
		this.deps.queue.enqueueUpsert(file.path);
	}

	onDelete(file: TAbstractFile): void {
		if (!this.shouldTrack(file)) return;
		this.resetIdleStreak();
		this.deps.queue.enqueueDelete(file.path);
		void this.deps.saveSettings((s) => {
			s.tombstones[file.path] = Date.now();
		});
	}

	onRename(file: TAbstractFile, oldPath: string): void {
		if (!this.shouldTrack(file)) return;
		this.resetIdleStreak();
		const settings = this.deps.getSettings();
		if (this.isExcluded(file.path, settings)) {
			this.deps.queue.enqueueDelete(oldPath);
			void this.deps.saveSettings((s) => {
				s.tombstones[oldPath] = Date.now();
			});
			return;
		}
		this.deps.queue.enqueueRename(oldPath, file.path);
	}

	onMetadataChanged(file: TFile, _data: string, _cache: CachedMetadata): void {
		if (!this.shouldTrack(file)) return;
		const settings = this.deps.getSettings();
		if (this.isExcluded(file.path, settings)) return;
		if (!this.isMarkdown(file)) return;
		// Metadata is fresh now — cancel the deferred upsert and enqueue immediately.
		const pending = this.pendingMdEdits.get(file.path);
		if (pending) {
			pending.cancel();
			this.pendingMdEdits.delete(file.path);
		}
		this.deps.queue.enqueueUpsert(file.path);
	}

	private scheduleMdUpsert(path: string): void {
		let pending = this.pendingMdEdits.get(path);
		if (!pending) {
			// resetTimer: true → each edit pushes the upsert out by another PENDING_DEBOUNCE_MS.
			pending = debounce(
				() => {
					this.pendingMdEdits.delete(path);
					this.deps.queue.enqueueUpsert(path);
				},
				PENDING_DEBOUNCE_MS,
				true,
			);
			this.pendingMdEdits.set(path, pending);
		}
		pending();
	}

	// ---- queue draining ---------------------------------------------------

	async flushQueue(): Promise<void> {
		if (this.deps.queue.size === 0) return;
		// Shared gate for every flush trigger so the first /sync can't race /connect.
		if (!this.deps.getSettings().connectorId) {
			const connected = await this.ensureConnected();
			if (!connected) return;
			if (!this.deps.getSettings().connectorId) return;
		}
		this.setStatus("syncing", `Syncing ${this.deps.queue.size} item(s)…`);
		const summary = await this.deps.queue.drain({
			processBatch: (batch) => this.processBatch(batch),
		});
		if (summary.acked > 0) {
			await this.deps.saveSettings((s) => {
				s.lastSyncAt = Date.now();
				s.filesSynced = (s.filesSynced ?? 0) + summary.acked;
			});
		}
		this.setStatus(this.queueStatusKind(), this.statusDetail());
	}

	private async processBatch(batch: QueueItem[]): Promise<BatchResult> {
		const settings = this.deps.getSettings();
		const upserts = batch.filter((b): b is QueueItem & { op: "upsert" } => b.op === "upsert");
		const renames = batch.filter((b): b is QueueItem & { op: "rename" } => b.op === "rename");
		const deletes = batch.filter((b): b is QueueItem & { op: "delete" } => b.op === "delete");

		const acked: QueueItem[] = [];
		const retry: QueueItem[] = [];
		const dropped: QueueItem[] = [];

		// Renames first so paths line up before content upserts.
		if (renames.length > 0) {
			try {
				const resp = await this.deps.apiClient.renameBatch({
					vaultId: settings.vaultId,
					renames: renames.map((r) => ({ oldPath: r.oldPath, newPath: r.newPath })),
				});
				const failed = new Set(
					resp.failed.map((f) => `${f.oldPath}\u0000${f.newPath}`),
				);
				for (const r of renames) {
					if (failed.has(`${r.oldPath}\u0000${r.newPath}`)) retry.push(r);
					else acked.push(r);
				}
			} catch (err) {
				if (await this.handleVaultNotRegistered(err)) {
					retry.push(...renames);
				} else {
					const verdict = this.classify(err);
					if (verdict === "stop") return { acked, retry: [...retry, ...renames], dropped, stop: true };
					if (verdict === "retry") retry.push(...renames);
					else dropped.push(...renames);
				}
			}
		}

		if (deletes.length > 0) {
			try {
				const resp = await this.deps.apiClient.deleteBatch({
					vaultId: settings.vaultId,
					paths: deletes.map((d) => d.path),
				});
				const failed = new Set(resp.failed);
				for (const d of deletes) {
					if (failed.has(d.path)) retry.push(d);
					else acked.push(d);
				}
			} catch (err) {
				if (await this.handleVaultNotRegistered(err)) {
					retry.push(...deletes);
				} else {
					const verdict = this.classify(err);
					if (verdict === "stop") return { acked, retry: [...retry, ...deletes], dropped, stop: true };
					if (verdict === "retry") retry.push(...deletes);
					else dropped.push(...deletes);
				}
			}
		}

		if (upserts.length > 0) {
			const payloads: NotePayload[] = [];
			for (const item of upserts) {
				const file = this.deps.app.vault.getFileByPath(item.path);
				if (!file) {
					// Vanished — ack now; the delete event will follow if needed.
					acked.push(item);
					continue;
				}
				try {
					const payload = this.isMarkdown(file)
						? await buildNotePayload(this.deps.app, file, settings.vaultId)
						: await this.buildBinaryPayload(file, settings.vaultId);
					payloads.push(payload);
				} catch (err) {
					console.error("SurfSense: failed to build payload", item.path, err);
					retry.push(item);
				}
			}

			if (payloads.length > 0) {
				try {
					const resp = await this.deps.apiClient.syncBatch({
						vaultId: settings.vaultId,
						notes: payloads,
					});
					// Per-note failures retry; queue maxAttempts drops poison pills.
					const failed = new Set(resp.failed);
					for (const item of upserts) {
						if (retry.find((r) => r === item)) continue;
						if (failed.has(item.path)) retry.push(item);
						else acked.push(item);
					}
				} catch (err) {
					if (await this.handleVaultNotRegistered(err)) {
						for (const item of upserts) {
							if (retry.find((r) => r === item)) continue;
							retry.push(item);
						}
					} else {
						const verdict = this.classify(err);
						if (verdict === "stop")
							return { acked, retry: [...retry, ...upserts], dropped, stop: true };
						if (verdict === "retry") retry.push(...upserts);
						else dropped.push(...upserts);
					}
				}
			}
		}

		return { acked, retry, dropped, stop: false };
	}

	private async buildBinaryPayload(file: TFile, vaultId: string): Promise<NotePayload> {
		// Attachments skip buildNotePayload (no markdown metadata) but still
		// need raw bytes + hash + stat so the backend can ETL-extract text
		// and manifest diff still works.
		const buf = await this.deps.app.vault.readBinary(file);
		const digest = await crypto.subtle.digest("SHA-256", buf);
		const hash = bufferToHex(digest);
		const binaryBase64 = arrayBufferToBase64(buf);
		return {
			vault_id: vaultId,
			path: file.path,
			name: file.basename,
			extension: file.extension,
			content: "",
			frontmatter: {},
			tags: [],
			headings: [],
			resolved_links: [],
			unresolved_links: [],
			embeds: [],
			aliases: [],
			content_hash: hash,
			size: file.stat.size,
			mtime: file.stat.mtime,
			ctime: file.stat.ctime,
			is_binary: true,
			binary_base64: binaryBase64,
			mime_type: mimeTypeFor(file.extension),
		};
	}

	// ---- reconcile --------------------------------------------------------

	async maybeReconcile(force = false): Promise<void> {
		const settings = this.deps.getSettings();
		if (!settings.connectorId) return;
		if (!force && settings.lastReconcileAt) {
			if (Date.now() - settings.lastReconcileAt < RECONCILE_MIN_INTERVAL_MS) return;
		}

		// Re-handshake first: if the vault grew enough to match another
		// device's fingerprint, the server merges and routes us to the
		// survivor row, which the /manifest call below then uses.
		const connected = await this.ensureConnected();
		if (!connected) return;
		const refreshed = this.deps.getSettings();
		if (!refreshed.connectorId) return;

		this.setStatus("syncing", "Reconciling vault with server…");
		try {
			const manifest = await this.deps.apiClient.getManifest(refreshed.vaultId);
			const remote = manifest.items ?? {};
			const enqueued = this.diffAndQueue(refreshed, remote);
			await this.deps.saveSettings((s) => {
				s.lastReconcileAt = Date.now();
				s.tombstones = pruneTombstones(s.tombstones);
			});
			this.updateIdleStreak(enqueued);
			await this.flushQueue();
		} catch (err) {
			this.classifyAndStatus(err, "Reconcile failed");
		}
	}

	/**
	 * Diff local vault vs server manifest and enqueue work. Skips disk reads
	 * on idle reconciles by short-circuiting on `mtime + size`; false positives
	 * collapse to a no-op upsert via the server's `content_hash` check.
	 * Returns the enqueued count to drive adaptive backoff.
	 */
	private diffAndQueue(
		settings: SyncEngineSettings,
		remote: Record<string, ManifestEntry>,
	): number {
		const localFiles = this.deps.app.vault.getFiles().filter((f) => {
			if (!this.shouldTrack(f)) return false;
			if (this.isExcluded(f.path, settings)) return false;
			return true;
		});
		const localPaths = new Set(localFiles.map((f) => f.path));
		let enqueued = 0;

		for (const file of localFiles) {
			const remoteEntry = remote[file.path];
			if (!remoteEntry) {
				this.deps.queue.enqueueUpsert(file.path);
				enqueued++;
				continue;
			}
			const remoteMtimeMs = toMillis(remoteEntry.mtime);
			const mtimeMatches = file.stat.mtime <= remoteMtimeMs + 1000;
			// Older server rows lack `size` — treat as unknown and re-upsert.
			const sizeMatches =
				typeof remoteEntry.size === "number" && file.stat.size === remoteEntry.size;
			if (mtimeMatches && sizeMatches) continue;
			this.deps.queue.enqueueUpsert(file.path);
			enqueued++;
		}

		// Remote-only → delete, unless a fresh tombstone is already in the queue.
		for (const path of Object.keys(remote)) {
			if (localPaths.has(path)) continue;
			const tombstone = settings.tombstones[path];
			if (tombstone && Date.now() - tombstone < TOMBSTONE_TTL_MS) continue;
			this.deps.queue.enqueueDelete(path);
			enqueued++;
		}

		return enqueued;
	}

	/** Bump (idle) or reset (active) the streak; notify only when the capped multiplier changes. */
	private updateIdleStreak(enqueued: number): void {
		const previousStreak = this.idleReconcileStreak;
		if (enqueued === 0) this.idleReconcileStreak++;
		else this.idleReconcileStreak = 0;
		const cap = Math.log2(this.maxBackoffMultiplier);
		const cappedPrev = Math.min(previousStreak, cap);
		const cappedNow = Math.min(this.idleReconcileStreak, cap);
		if (cappedPrev !== cappedNow) this.deps.onReconcileBackoffChanged?.();
	}

	/** Vault edit — drop back to base interval immediately. */
	private resetIdleStreak(): void {
		if (this.idleReconcileStreak === 0) return;
		this.idleReconcileStreak = 0;
		this.deps.onReconcileBackoffChanged?.();
	}

	// ---- status helpers ---------------------------------------------------

	private setStatus(kind: StatusKind, detail?: string): void {
		this.deps.setStatus({ kind, detail, queueDepth: this.deps.queue.size });
	}

	private queueStatusKind(): StatusKind {
		if (this.deps.queue.size > 0) return "queued";
		return "idle";
	}

	private statusDetail(): string | undefined {
		const settings = this.deps.getSettings();
		if (settings.lastSyncAt) {
			return `Last sync ${formatRelative(settings.lastSyncAt)}`;
		}
		return undefined;
	}

	private handleStartupError(err: unknown): void {
		if (err instanceof AuthError) {
			this.setStatus("auth-error", err.message);
			return;
		}
		if (err instanceof TransientError) {
			this.setStatus("offline", err.message);
			return;
		}
		this.setStatus("error", (err as Error).message ?? "Unknown error");
	}

	/** Re-connect on VAULT_NOT_REGISTERED so the next drain sees the new row. */
	private async handleVaultNotRegistered(err: unknown): Promise<boolean> {
		if (!(err instanceof VaultNotRegisteredError)) return false;
		console.warn("SurfSense: vault not registered, re-connecting before retry", err);
		await this.ensureConnected();
		return true;
	}

	private classify(err: unknown): "ack" | "retry" | "drop" | "stop" {
		if (err instanceof AuthError) {
			this.setStatus("auth-error", err.message);
			return "stop";
		}
		if (err instanceof TransientError) {
			this.setStatus("offline", err.message);
			return "stop";
		}
		if (err instanceof PermanentError) {
			console.warn("SurfSense: permanent error, dropping batch", err);
			new Notice(`Surfsense: ${err.message}`);
			return "drop";
		}
		console.error("SurfSense: unknown error", err);
		return "retry";
	}

	private classifyAndStatus(err: unknown, prefix: string): void {
		const verdict = this.classify(err);
		if (verdict === "stop") return;
		this.setStatus(this.queueStatusKind(), `${prefix}: ${(err as Error).message}`);
	}

	// ---- predicates -------------------------------------------------------

	private shouldTrack(file: TAbstractFile): boolean {
		if (!isTFile(file)) return false;
		if (this.isMarkdown(file)) return true;
		const settings = this.deps.getSettings();
		if (!settings.includeAttachments) return false;
		return ALLOWED_ATTACHMENT_EXTENSIONS.has(file.extension.toLowerCase());
	}

	private isExcluded(path: string, settings: SyncEngineSettings): boolean {
		if (isFolderFiltered(path, settings.includeFolders, settings.excludeFolders)) {
			return true;
		}
		return isExcluded(path, settings.excludePatterns);
	}

	private isMarkdown(file: TAbstractFile): boolean {
		return isTFile(file) && file.extension.toLowerCase() === "md";
	}
}

function isTFile(f: TAbstractFile): f is TFile {
	return f instanceof TFile;
}

function bufferToHex(buf: ArrayBuffer): string {
	const view = new Uint8Array(buf);
	let hex = "";
	for (let i = 0; i < view.length; i++) hex += (view[i] ?? 0).toString(16).padStart(2, "0");
	return hex;
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
	const bytes = new Uint8Array(buf);
	const chunkSize = 0x8000;
	let binary = "";
	for (let i = 0; i < bytes.length; i += chunkSize) {
		const chunk = bytes.subarray(i, i + chunkSize);
		binary += String.fromCharCode(...Array.from(chunk));
	}
	return btoa(binary);
}

/** Source of truth for the attachment whitelist. Mirrors ATTACHMENT_MIME_TYPES on the backend. */
export const MIME_BY_EXTENSION = {
	pdf: "application/pdf",
	png: "image/png",
	jpg: "image/jpeg",
	jpeg: "image/jpeg",
	gif: "image/gif",
	webp: "image/webp",
	svg: "image/svg+xml",
	txt: "text/plain",
} as const satisfies Record<string, string>;

export const ALLOWED_ATTACHMENT_EXTENSIONS: ReadonlySet<string> = new Set(
	Object.keys(MIME_BY_EXTENSION),
);

function mimeTypeFor(extension: string): string {
	const ext = extension.toLowerCase() as keyof typeof MIME_BY_EXTENSION;
	const mime = MIME_BY_EXTENSION[ext];
	if (!mime) {
		throw new Error(`Unsupported attachment extension: .${extension}`);
	}
	return mime;
}

function formatRelative(ts: number): string {
	const diff = Date.now() - ts;
	if (diff < 60_000) return "just now";
	if (diff < 3600_000) return `${Math.round(diff / 60_000)}m ago`;
	if (diff < 86_400_000) return `${Math.round(diff / 3600_000)}h ago`;
	return `${Math.round(diff / 86_400_000)}d ago`;
}

/** Manifest mtimes arrive as ISO strings, vault stats as epoch ms — normalise. */
function toMillis(value: number | string | Date): number {
	if (typeof value === "number") return value;
	if (value instanceof Date) return value.getTime();
	const parsed = Date.parse(value);
	return Number.isFinite(parsed) ? parsed : 0;
}

function pruneTombstones(tombstones: Record<string, number>): Record<string, number> {
	const out: Record<string, number> = {};
	const cutoff = Date.now() - TOMBSTONE_TTL_MS;
	for (const [k, v] of Object.entries(tombstones)) {
		if (v >= cutoff) out[k] = v;
	}
	return out;
}
