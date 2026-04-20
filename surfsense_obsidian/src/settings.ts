import {
	type App,
	Notice,
	PluginSettingTab,
	Setting,
} from "obsidian";
import { AuthError } from "./api-client";
import { parseExcludePatterns } from "./excludes";
import type SurfSensePlugin from "./main";
import type { SearchSpace } from "./types";

/** Plugin settings tab. */

export class SurfSenseSettingTab extends PluginSettingTab {
	private readonly plugin: SurfSensePlugin;
	private searchSpaces: SearchSpace[] = [];
	private loadingSpaces = false;
	private statusEl: HTMLElement | null = null;

	constructor(app: App, plugin: SurfSensePlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();
		containerEl.addClass("surfsense-settings");

		const settings = this.plugin.settings;

		new Setting(containerEl).setName("Connection").setHeading();

		new Setting(containerEl)
			.setName("Server URL")
			.setDesc(
				"https://api.surfsense.com for SurfSense Cloud, or your self-hosted URL.",
			)
			.addText((text) =>
				text
					.setPlaceholder("https://api.surfsense.com")
					.setValue(settings.serverUrl)
					.onChange(async (value) => {
						this.plugin.settings.serverUrl = value.trim();
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("API token")
			.setDesc(
				"Paste your Surfsense API token (expires after 24 hours; re-paste when you see an auth error).",
			)
			.addText((text) => {
				text.inputEl.type = "password";
				text.inputEl.autocomplete = "off";
				text.inputEl.spellcheck = false;
				text
					.setPlaceholder("Paste token")
					.setValue(settings.apiToken)
					.onChange(async (value) => {
						this.plugin.settings.apiToken = value.trim();
						await this.plugin.saveSettings();
					});
			})
			.addButton((btn) =>
				btn
					.setButtonText("Verify")
					.setCta()
					.onClick(async () => {
						btn.setDisabled(true);
						try {
							await this.plugin.api.verifyToken();
							new Notice("Surfsense: token verified.");
							await this.refreshSearchSpaces();
							this.display();
						} catch (err) {
							this.handleApiError(err);
						} finally {
							btn.setDisabled(false);
						}
					}),
			);

		new Setting(containerEl)
			.setName("Search space")
			.setDesc(
				"Which Surfsense search space this vault syncs into. Reload after changing your token.",
			)
			.addDropdown((drop) => {
				drop.addOption("", this.loadingSpaces ? "Loading…" : "Select a search space");
				for (const space of this.searchSpaces) {
					drop.addOption(String(space.id), space.name);
				}
				if (settings.searchSpaceId !== null) {
					drop.setValue(String(settings.searchSpaceId));
				}
				drop.onChange(async (value) => {
					this.plugin.settings.searchSpaceId = value ? Number(value) : null;
					this.plugin.settings.connectorId = null;
					await this.plugin.saveSettings();
					if (this.plugin.settings.searchSpaceId !== null) {
						try {
							await this.plugin.engine.ensureConnected();
							new Notice("Surfsense: vault connected.");
						} catch (err) {
							this.handleApiError(err);
						}
					}
					this.renderStatus();
				});
			})
			.addExtraButton((btn) =>
				btn
					.setIcon("refresh-ccw")
					.setTooltip("Reload search spaces")
					.onClick(async () => {
						await this.refreshSearchSpaces();
						this.display();
					}),
			);

		new Setting(containerEl).setName("Vault").setHeading();

		new Setting(containerEl)
			.setName("Vault name")
			.setDesc(
				"Friendly name for this vault. Defaults to your Obsidian vault folder name.",
			)
			.addText((text) =>
				text
					.setValue(settings.vaultName)
					.onChange(async (value) => {
						this.plugin.settings.vaultName = value.trim() || this.app.vault.getName();
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Sync mode")
			.setDesc("Auto syncs on every edit. Manual only syncs when you trigger it via the command palette.")
			.addDropdown((drop) =>
				drop
					.addOption("auto", "Auto")
					.addOption("manual", "Manual")
					.setValue(settings.syncMode)
					.onChange(async (value) => {
						this.plugin.settings.syncMode = value === "manual" ? "manual" : "auto";
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Exclude patterns")
			.setDesc(
				"One pattern per line. Supports * and **. Lines starting with # are comments. Files matching any pattern are skipped.",
			)
			.addTextArea((area) => {
				area.inputEl.rows = 4;
				area
					.setPlaceholder(".trash\n_attachments\ntemplates/**")
					.setValue(settings.excludePatterns.join("\n"))
					.onChange(async (value) => {
						this.plugin.settings.excludePatterns = parseExcludePatterns(value);
						await this.plugin.saveSettings();
					});
			});

		new Setting(containerEl)
			.setName("Include attachments")
			.setDesc(
				"Sync non-Markdown files (images, PDFs, …). Off by default — Markdown only.",
			)
			.addToggle((toggle) =>
				toggle
					.setValue(settings.includeAttachments)
					.onChange(async (value) => {
						this.plugin.settings.includeAttachments = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl).setName("Identity").setHeading();

		new Setting(containerEl)
			.setName("Vault ID")
			.setDesc(
				"Stable identifier for this vault. Used by the backend to keep separate vaults distinct even if their folder names change.",
			)
			.addText((text) => {
				text.inputEl.disabled = true;
				text.setValue(settings.vaultId);
			});

		// Device ID is deliberately not exposed: it's an opaque per-install UUID
		// (see seedIdentity in main.ts) and the web UI only shows a device count.

		new Setting(containerEl).setName("Status").setHeading();
		this.statusEl = containerEl.createDiv({ cls: "surfsense-settings__status" });
		this.renderStatus();

		new Setting(containerEl)
			.addButton((btn) =>
				btn
					.setButtonText("Re-sync entire vault")
					.onClick(async () => {
						btn.setDisabled(true);
						try {
							await this.plugin.engine.maybeReconcile(true);
							new Notice("Surfsense: re-sync requested.");
						} catch (err) {
							this.handleApiError(err);
						} finally {
							btn.setDisabled(false);
							this.renderStatus();
						}
					}),
			)
			.addButton((btn) =>
				btn.setButtonText("Open releases").onClick(() => {
					window.open(
						"https://github.com/MODSetter/SurfSense/releases?q=obsidian",
						"_blank",
					);
				}),
			);
	}

	hide(): void {
		this.statusEl = null;
	}

	private async refreshSearchSpaces(): Promise<void> {
		this.loadingSpaces = true;
		try {
			this.searchSpaces = await this.plugin.api.listSearchSpaces();
		} catch (err) {
			this.handleApiError(err);
			this.searchSpaces = [];
		} finally {
			this.loadingSpaces = false;
		}
	}

	renderStatus(): void {
		if (!this.statusEl) return;
		const s = this.plugin.settings;
		this.statusEl.empty();

		const rows: { label: string; value: string }[] = [
			{ label: "Status", value: this.plugin.lastStatus.kind },
			{
				label: "Last sync",
				value: s.lastSyncAt ? new Date(s.lastSyncAt).toLocaleString() : "—",
			},
			{
				label: "Last reconcile",
				value: s.lastReconcileAt ? new Date(s.lastReconcileAt).toLocaleString() : "—",
			},
			{ label: "Files synced", value: String(s.filesSynced ?? 0) },
			{ label: "Queue depth", value: String(this.plugin.queueDepth) },
			{
				label: "API version",
				value: this.plugin.serverApiVersion ?? "(not yet handshaken)",
			},
			{
				label: "Capabilities",
				value: this.plugin.serverCapabilities.length
					? this.plugin.serverCapabilities.join(", ")
					: "(not yet handshaken)",
			},
		];
		for (const row of rows) {
			const wrap = this.statusEl.createDiv({ cls: "surfsense-settings__status-row" });
			wrap.createSpan({ cls: "surfsense-settings__status-label", text: row.label });
			wrap.createSpan({ cls: "surfsense-settings__status-value", text: row.value });
		}
	}

	private handleApiError(err: unknown): void {
		if (err instanceof AuthError) {
			new Notice(`SurfSense: ${err.message}`);
			return;
		}
		new Notice(
			`SurfSense: request failed — ${(err as Error).message ?? "unknown error"}`,
		);
	}
}
