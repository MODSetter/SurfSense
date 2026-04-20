import { Notice, TFile, type App, type CachedMetadata, type TAbstractFile } from "obsidian";
import {
	AuthError,
	PermanentError,
	type SurfSenseApiClient,
	TransientError,
	VaultNotRegisteredError,
} from "./api-client";
import { isExcluded, isFolderFiltered } from "./excludes";
import { buildNotePayload, computeContentHash } from "./payload";
import { type BatchResult, PersistentQueue } from "./queue";
import type {
	HealthResponse,
	NotePayload,
	QueueItem,
	StatusKind,
	StatusState,
} from "./types";

/**
 * Owner of "what does the vault look like vs the server" reasoning.
 *
 * Start order: connect (or fall back to /health) → drain queue → reconcile →
 * subscribe events. Reconcile no-ops if last run was < RECONCILE_MIN_INTERVAL_MS ago.
 */

export interface SyncEngineDeps {
	app: App;
	apiClient: SurfSenseApiClient;
	queue: PersistentQueue;
	getSettings: () => SyncEngineSettings;
	saveSettings: (mut: (s: SyncEngineSettings) => void) => Promise<void>;
	setStatus: (s: StatusState) => void;
	onCapabilities: (caps: string[]) => void;
}

export interface SyncEngineSettings {
	vaultId: string;
	connectorId: number | null;
	searchSpaceId: number | null;
	includeFolders: string[];
	excludeFolders: string[];
	excludePatterns: string[];
	includeAttachments: boolean;
	syncMode: "auto" | "manual";
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
	private pendingMdEdits = new Map<string, ReturnType<typeof setTimeout>>();

	constructor(deps: SyncEngineDeps) {
		this.deps = deps;
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
			// No target yet — bare /health probe still surfaces auth/network errors.
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
		// flushQueue owns the connectorId gate, so a failed connect here still
		// leaves the queue stable for the next trigger.
		await this.ensureConnected();

		await this.flushQueue();
		await this.maybeReconcile();
		this.setStatus(this.queueStatusKind(), undefined);
	}

	/** Public entry point used after settings save to (re)connect the vault. */
	async ensureConnected(): Promise<void> {
		const settings = this.deps.getSettings();
		if (!settings.searchSpaceId) {
			this.setStatus("idle", "Pick a search space in settings.");
			return;
		}
		try {
			const resp = await this.deps.apiClient.connect({
				searchSpaceId: settings.searchSpaceId,
				vaultId: settings.vaultId,
				vaultName: this.deps.app.vault.getName(),
			});
			this.applyHealth(resp);
			await this.deps.saveSettings((s) => {
				s.connectorId = resp.connector_id;
			});
		} catch (err) {
			this.handleStartupError(err);
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
		if (this.isMarkdown(file)) {
			// Defer to metadataCache.changed so payload fields are fresh.
			this.scheduleMdUpsert(file.path);
			return;
		}
		this.deps.queue.enqueueUpsert(file.path);
	}

	onDelete(file: TAbstractFile): void {
		if (!this.shouldTrack(file)) return;
		this.deps.queue.enqueueDelete(file.path);
		void this.deps.saveSettings((s) => {
			s.tombstones[file.path] = Date.now();
		});
	}

	onRename(file: TAbstractFile, oldPath: string): void {
		if (!this.shouldTrack(file)) return;
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
		// Cancel any deferred upsert and enqueue with fresh metadata now.
		const pending = this.pendingMdEdits.get(file.path);
		if (pending) {
			clearTimeout(pending);
			this.pendingMdEdits.delete(file.path);
		}
		this.deps.queue.enqueueUpsert(file.path);
	}

	private scheduleMdUpsert(path: string): void {
		const existing = this.pendingMdEdits.get(path);
		if (existing) clearTimeout(existing);
		this.pendingMdEdits.set(
			path,
			setTimeout(() => {
				this.pendingMdEdits.delete(path);
				this.deps.queue.enqueueUpsert(path);
			}, PENDING_DEBOUNCE_MS),
		);
	}

	// ---- queue draining ---------------------------------------------------

	async flushQueue(): Promise<void> {
		if (this.deps.queue.size === 0) return;
		// Shared gate for every flush trigger so the first /sync can't race /connect.
		if (!this.deps.getSettings().connectorId) {
			await this.ensureConnected();
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

		// Renames first so paths line up server-side before content upserts.
		if (renames.length > 0) {
			try {
				await this.deps.apiClient.renameBatch({
					vaultId: settings.vaultId,
					renames: renames.map((r) => ({ oldPath: r.oldPath, newPath: r.newPath })),
				});
				acked.push(...renames);
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
				await this.deps.apiClient.deleteBatch({
					vaultId: settings.vaultId,
					paths: deletes.map((d) => d.path),
				});
				acked.push(...deletes);
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
				const file = this.deps.app.vault.getAbstractFileByPath(item.path);
				if (!file || !isTFile(file)) {
					// File vanished; treat as ack (delete will follow if user removed it).
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
					const rejected = new Set(resp.rejected ?? []);
					for (const item of upserts) {
						if (retry.find((r) => r === item)) continue;
						if (rejected.has(item.path)) dropped.push(item);
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
		// Plain attachments don't go through buildNotePayload (no markdown
		// metadata to extract). We still need a stable hash + file stat so
		// the backend can de-dupe and the manifest diff still works.
		const buf = await this.deps.app.vault.readBinary(file);
		const digest = await crypto.subtle.digest("SHA-256", buf);
		const hash = bufferToHex(digest);
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
			mtime: file.stat.mtime,
			ctime: file.stat.ctime,
			is_binary: true,
		};
	}

	// ---- reconcile --------------------------------------------------------

	async maybeReconcile(force = false): Promise<void> {
		const settings = this.deps.getSettings();
		if (!settings.connectorId) return;
		if (!force && settings.lastReconcileAt) {
			if (Date.now() - settings.lastReconcileAt < RECONCILE_MIN_INTERVAL_MS) return;
		}

		this.setStatus("syncing", "Reconciling vault with server…");
		try {
			const manifest = await this.deps.apiClient.getManifest(settings.vaultId);
			const remote = manifest.entries ?? {};
			await this.diffAndQueue(settings, remote);
			await this.deps.saveSettings((s) => {
				s.lastReconcileAt = Date.now();
				s.tombstones = pruneTombstones(s.tombstones);
			});
			await this.flushQueue();
		} catch (err) {
			this.classifyAndStatus(err, "Reconcile failed");
		}
	}

	private async diffAndQueue(
		settings: SyncEngineSettings,
		remote: Record<string, { hash: string; mtime: number }>,
	): Promise<void> {
		const localFiles = this.deps.app.vault.getFiles().filter((f) => {
			if (!this.shouldTrack(f)) return false;
			if (this.isExcluded(f.path, settings)) return false;
			return true;
		});
		const localPaths = new Set(localFiles.map((f) => f.path));

		// Local-only or content-changed → upsert.
		for (const file of localFiles) {
			const remoteEntry = remote[file.path];
			if (!remoteEntry) {
				this.deps.queue.enqueueUpsert(file.path);
				continue;
			}
			if (file.stat.mtime > remoteEntry.mtime + 1000) {
				this.deps.queue.enqueueUpsert(file.path);
				continue;
			}
			if (this.isMarkdown(file)) {
				const content = await this.deps.app.vault.cachedRead(file);
				const hash = await computeContentHash(content);
				if (hash !== remoteEntry.hash) {
					this.deps.queue.enqueueUpsert(file.path);
				}
			}
		}

		// Remote-only → delete, but only if NOT a fresh tombstone (which
		// the queue will deliver) and NOT a path we already plan to upsert.
		for (const path of Object.keys(remote)) {
			if (localPaths.has(path)) continue;
			const tombstone = settings.tombstones[path];
			if (tombstone && Date.now() - tombstone < TOMBSTONE_TTL_MS) continue;
			this.deps.queue.enqueueDelete(path);
		}
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
			new Notice(`SurfSense: ${err.message}`);
			return "drop";
		}
		console.error("SurfSense: unknown error", err);
		return "retry";
	}

	private classifyAndStatus(err: unknown, prefix: string): void {
		this.classify(err);
		this.setStatus(this.queueStatusKind(), `${prefix}: ${(err as Error).message}`);
	}

	// ---- predicates -------------------------------------------------------

	private shouldTrack(file: TAbstractFile): boolean {
		if (!isTFile(file)) return false;
		const settings = this.deps.getSettings();
		if (!settings.includeAttachments && !this.isMarkdown(file)) return false;
		return true;
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

function formatRelative(ts: number): string {
	const diff = Date.now() - ts;
	if (diff < 60_000) return "just now";
	if (diff < 3600_000) return `${Math.round(diff / 60_000)}m ago`;
	if (diff < 86_400_000) return `${Math.round(diff / 3600_000)}h ago`;
	return `${Math.round(diff / 86_400_000)}d ago`;
}

function pruneTombstones(tombstones: Record<string, number>): Record<string, number> {
	const out: Record<string, number> = {};
	const cutoff = Date.now() - TOMBSTONE_TTL_MS;
	for (const [k, v] of Object.entries(tombstones)) {
		if (v >= cutoff) out[k] = v;
	}
	return out;
}
