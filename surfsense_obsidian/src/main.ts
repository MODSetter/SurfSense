import { Notice, Plugin } from "obsidian";
import { SurfSenseApiClient } from "./api-client";
import { PersistentQueue } from "./queue";
import { SurfSenseSettingTab } from "./settings";
import { StatusBar } from "./status-bar";
import { SyncEngine } from "./sync-engine";
import {
	DEFAULT_SETTINGS,
	type QueueItem,
	type StatusState,
	type SurfsensePluginSettings,
} from "./types";

/**
 * SurfSense plugin entry point.
 *
 * Replaces the obsidian-sample-plugin SampleModal/ribbon stub. Lifecycle:
 *
 *   onload():
 *     load settings → seed identity (vault_id, device_id) →
 *     wire api client + queue + sync engine + status bar →
 *     register settings tab → register vault + metadataCache events →
 *     register commands (resync, sync current note, open settings) →
 *     register status bar item →
 *     kick off engine.start() (health → drain → reconcile).
 *
 *   onunload():
 *     stop the queue's debounce timer; unregistered events and DOM
 *     handles auto-clean via the Plugin base class.
 */
export default class SurfSensePlugin extends Plugin {
	settings!: SurfsensePluginSettings;
	api!: SurfSenseApiClient;
	queue!: PersistentQueue;
	engine!: SyncEngine;
	private statusBar: StatusBar | null = null;
	lastStatus: StatusState = { kind: "idle", queueDepth: 0 };
	serverCapabilities: string[] = [];
	serverApiVersion: string | null = null;
	private settingTab: SurfSenseSettingTab | null = null;

	async onload() {
		await this.loadSettings();
		this.seedIdentity();
		await this.saveSettings();

		const pluginVersion = this.manifest.version;

		this.api = new SurfSenseApiClient({
			getServerUrl: () => this.settings.serverUrl,
			getToken: () => this.settings.apiToken,
			pluginVersion,
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
				this.settingTab?.renderStatus();
			},
			setStatus: (s) => {
				this.lastStatus = s;
				this.statusBar?.update(s);
				this.settingTab?.renderStatus();
			},
			onCapabilities: (caps, apiVersion) => {
				this.serverCapabilities = [...caps];
				this.serverApiVersion = apiVersion;
				this.settingTab?.renderStatus();
			},
		});

		this.queue.setFlushHandler(() => {
			if (this.settings.syncMode !== "auto") return;
			void this.engine.flushQueue();
		});

		this.settingTab = new SurfSenseSettingTab(this.app, this);
		this.addSettingTab(this.settingTab);

		const statusHost = this.addStatusBarItem();
		this.statusBar = new StatusBar(statusHost);
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
			id: "open-settings",
			name: "Open settings",
			callback: () => {
				// Obsidian exposes this through the Setting host on the workspace;
				// fall back silently if the API moves so we never throw.
				type SettingHost = {
					open?: () => void;
					openTabById?: (id: string) => void;
				};
				const setting = (this.app as unknown as { setting?: SettingHost }).setting;
				if (setting?.open) setting.open();
				if (setting?.openTabById) setting.openTabById(this.manifest.id);
			},
		});

		// Kick off the start sequence after Obsidian finishes its own
		// startup work, so the metadataCache is warm before reconcile.
		this.app.workspace.onLayoutReady(() => {
			void this.engine.start();
		});
	}

	onunload() {
		this.queue?.cancelFlush();
		this.queue?.requestStop();
	}

	get queueDepth(): number {
		return this.queue?.size ?? 0;
	}

	async loadSettings() {
		const data = (await this.loadData()) as Partial<SurfsensePluginSettings> | null;
		this.settings = {
			...DEFAULT_SETTINGS,
			...(data ?? {}),
			queue: (data?.queue ?? []).map((i: QueueItem) => ({ ...i })),
			tombstones: { ...(data?.tombstones ?? {}) },
			excludePatterns: data?.excludePatterns?.length
				? [...data.excludePatterns]
				: [...DEFAULT_SETTINGS.excludePatterns],
		};
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	private seedIdentity(): void {
		if (!this.settings.vaultId) {
			this.settings.vaultId = generateUuid();
		}
		if (!this.settings.deviceId) {
			this.settings.deviceId = generateUuid();
		}
		if (!this.settings.vaultName) {
			this.settings.vaultName = this.app.vault.getName();
		}
	}
}

function generateUuid(): string {
	const c = globalThis.crypto;
	if (c?.randomUUID) return c.randomUUID();
	const buf = new Uint8Array(16);
	c.getRandomValues(buf);
	buf[6] = ((buf[6] ?? 0) & 0x0f) | 0x40;
	buf[8] = ((buf[8] ?? 0) & 0x3f) | 0x80;
	const hex = Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(
		16,
		20,
	)}-${hex.slice(20)}`;
}
