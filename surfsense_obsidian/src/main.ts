import { Notice, Platform, Plugin } from "obsidian";
import { SurfSenseApiClient } from "./api-client";
import { PersistentQueue } from "./queue";
import { SurfSenseSettingTab } from "./settings";
import { StatusBar } from "./status-bar";
import { StatusModal } from "./status-modal";
import { SyncEngine } from "./sync-engine";
import {
	DEFAULT_SETTINGS,
	type QueueItem,
	type StatusState,
	type SurfsensePluginSettings,
} from "./types";
import { generateVaultUuid } from "./vault-identity";

/** SurfSense plugin entry point. */
export default class SurfSensePlugin extends Plugin {
	settings!: SurfsensePluginSettings;
	api!: SurfSenseApiClient;
	queue!: PersistentQueue;
	engine!: SyncEngine;
	private statusBar: StatusBar | null = null;
	lastStatus: StatusState = { kind: "idle", queueDepth: 0 };
	serverCapabilities: string[] = [];
	private settingTab: SurfSenseSettingTab | null = null;
	private statusListeners = new Set<() => void>();
	private reconcileTimerId: number | null = null;

	async onload() {
		await this.loadSettings();
		this.seedIdentity();
		await this.saveSettings();

		this.api = new SurfSenseApiClient({
			getServerUrl: () => this.settings.serverUrl,
			getToken: () => this.settings.apiToken,
		});

		this.queue = new PersistentQueue(this.settings.queue ?? [], {
			persist: async (items) => {
				this.settings.queue = items;
				await this.saveData(this.settings);
			},
		});

		this.engine = new SyncEngine({
			app: this.app,
			apiClient: this.api,
			queue: this.queue,
			getSettings: () => this.settings,
			saveSettings: async (mut) => {
				mut(this.settings);
				await this.saveSettings();
				this.notifyStatusChange();
			},
			setStatus: (s) => {
				this.lastStatus = s;
				this.statusBar?.update(s);
				this.notifyStatusChange();
			},
			onCapabilities: (caps) => {
				this.serverCapabilities = [...caps];
				this.notifyStatusChange();
			},
			onReconcileBackoffChanged: () => {
				this.restartReconcileTimer();
			},
		});

		this.queue.setFlushHandler(() => {
			if (!this.shouldAutoSync()) return;
			void this.engine.flushQueue();
		});

		this.settingTab = new SurfSenseSettingTab(this.app, this);
		this.addSettingTab(this.settingTab);

		const statusHost = this.addStatusBarItem();
		this.statusBar = new StatusBar(statusHost, () => this.openStatusModal());
		this.statusBar.update(this.lastStatus);

		this.registerEvent(
			this.app.vault.on("create", (file) => this.engine.onCreate(file)),
		);
		this.registerEvent(
			this.app.vault.on("modify", (file) => this.engine.onModify(file)),
		);
		this.registerEvent(
			this.app.vault.on("delete", (file) => this.engine.onDelete(file)),
		);
		this.registerEvent(
			this.app.vault.on("rename", (file, oldPath) =>
				this.engine.onRename(file, oldPath),
			),
		);
		this.registerEvent(
			this.app.metadataCache.on("changed", (file, data, cache) =>
				this.engine.onMetadataChanged(file, data, cache),
			),
		);

		this.addCommand({
			id: "resync-vault",
			name: "Re-sync entire vault",
			callback: async () => {
				try {
					await this.engine.maybeReconcile(true);
					new Notice("Surfsense: re-sync started.");
				} catch (err) {
					new Notice(`Surfsense: re-sync failed — ${(err as Error).message}`);
				}
			},
		});

		this.addCommand({
			id: "sync-current-note",
			name: "Sync current note",
			checkCallback: (checking) => {
				const file = this.app.workspace.getActiveFile();
				if (!file || file.extension.toLowerCase() !== "md") return false;
				if (checking) return true;
				this.queue.enqueueUpsert(file.path);
				void this.engine.flushQueue();
				return true;
			},
		});

		this.addCommand({
			id: "open-status",
			name: "Open sync status",
			callback: () => this.openStatusModal(),
		});

		this.addCommand({
			id: "open-settings",
			name: "Open settings",
			callback: () => {
				// `app.setting` isn't in the d.ts; fall back silently if it moves.
				type SettingHost = {
					open?: () => void;
					openTabById?: (id: string) => void;
				};
				const setting = (this.app as unknown as { setting?: SettingHost }).setting;
				if (setting?.open) setting.open();
				if (setting?.openTabById) setting.openTabById(this.manifest.id);
			},
		});

		const onNetChange = () => {
			if (this.shouldAutoSync()) void this.engine.flushQueue();
		};
		this.registerDomEvent(window, "online", onNetChange);
		const conn = (navigator as unknown as { connection?: NetworkConnection }).connection;
		if (conn && typeof conn.addEventListener === "function") {
			conn.addEventListener("change", onNetChange);
			this.register(() => conn.removeEventListener?.("change", onNetChange));
		}

		// Wait for layout so the metadataCache is warm before reconcile.
		this.app.workspace.onLayoutReady(() => {
			void this.engine.start();
			this.restartReconcileTimer();
		});
	}

	onunload() {
		this.queue?.cancelFlush();
		this.queue?.requestStop();
	}

	/**
	 * Obsidian fires this when another device rewrites our data.json.
	 * If the synced vault_id differs from ours, adopt it and
	 * re-handshake so the server routes us to the right row.
	 */
	async onExternalSettingsChange(): Promise<void> {
		const previousVaultId = this.settings.vaultId;
		const previousConnectorId = this.settings.connectorId;
		await this.loadSettings();
		const changed =
			this.settings.vaultId !== previousVaultId ||
			this.settings.connectorId !== previousConnectorId;
		if (!changed) return;
		this.notifyStatusChange();
		if (this.settings.searchSpaceId !== null) {
			void this.engine.ensureConnected();
		}
	}

	get queueDepth(): number {
		return this.queue?.size ?? 0;
	}

	openStatusModal(): void {
		new StatusModal(this.app, this).open();
	}

	restartReconcileTimer(): void {
		if (this.reconcileTimerId !== null) {
			window.clearInterval(this.reconcileTimerId);
			this.reconcileTimerId = null;
		}
		const minutes = this.settings.syncIntervalMinutes ?? 10;
		if (minutes <= 0) return;
		const baseMs = minutes * 60 * 1000;
		// Idle vaults back off (×2 → ×4 → ×8); resets on the first edit or non-empty reconcile.
		const effectiveMs = this.engine?.getReconcileBackoffMs(baseMs) ?? baseMs;
		const id = window.setInterval(
			() => {
				if (!this.shouldAutoSync()) return;
				void this.engine.maybeReconcile();
			},
			effectiveMs,
		);
		this.reconcileTimerId = id;
		this.registerInterval(id);
	}

	/** Gate for background network activity; per-edit flush + periodic reconcile both consult this. */
	shouldAutoSync(): boolean {
		if (!this.settings.wifiOnly) return true;
		if (!Platform.isMobileApp) return true;
		// navigator.connection is supported on Android Capacitor; undefined on iOS.
		// When unavailable, behave permissively so iOS users aren't blocked outright.
		const conn = (navigator as unknown as { connection?: NetworkConnection }).connection;
		if (!conn || typeof conn.type !== "string") return true;
		return conn.type === "wifi" || conn.type === "ethernet";
	}

	onStatusChange(listener: () => void): void {
		this.statusListeners.add(listener);
	}

	offStatusChange(listener: () => void): void {
		this.statusListeners.delete(listener);
	}

	private notifyStatusChange(): void {
		for (const fn of this.statusListeners) fn();
	}

	async loadSettings() {
		const data = (await this.loadData()) as Partial<SurfsensePluginSettings> | null;
		this.settings = {
			...DEFAULT_SETTINGS,
			...(data ?? {}),
			queue: (data?.queue ?? []).map((i: QueueItem) => ({ ...i })),
			tombstones: { ...(data?.tombstones ?? {}) },
			includeFolders: [...(data?.includeFolders ?? [])],
			excludeFolders: [...(data?.excludeFolders ?? [])],
			excludePatterns: data?.excludePatterns?.length
				? [...data.excludePatterns]
				: [...DEFAULT_SETTINGS.excludePatterns],
		};
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	/**
	 * Mint a tentative vault_id locally on first run. The server's
	 * fingerprint dedup (see /obsidian/connect) may overwrite it on the
	 * first /connect when another device of the same vault has already
	 * registered; we always trust the server's response.
	 */
	private seedIdentity(): void {
		if (!this.settings.vaultId) {
			this.settings.vaultId = generateVaultUuid();
		}
	}
}

/** Subset of the Network Information API used to detect WiFi vs cellular on Android. */
interface NetworkConnection {
	type?: string;
	addEventListener?: (event: string, handler: () => void) => void;
	removeEventListener?: (event: string, handler: () => void) => void;
}
