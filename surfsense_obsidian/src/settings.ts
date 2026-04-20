import {
	type App,
	Notice,
	PluginSettingTab,
	Setting,
} from "obsidian";
import { AuthError } from "./api-client";
import { normalizeFolder, parseExcludePatterns } from "./excludes";
import { FolderSuggestModal } from "./folder-suggest-modal";
import type SurfSensePlugin from "./main";
import type { SearchSpace } from "./types";

/** Plugin settings tab. */

export class SurfSenseSettingTab extends PluginSettingTab {
	private readonly plugin: SurfSensePlugin;
	private searchSpaces: SearchSpace[] = [];
	private loadingSpaces = false;

	constructor(app: App, plugin: SurfSensePlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

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

		this.renderFolderList(
			containerEl,
			"Include folders",
			"Folders to sync (leave empty to sync entire vault).",
			settings.includeFolders,
			(next) => {
				this.plugin.settings.includeFolders = next;
			},
		);

		this.renderFolderList(
			containerEl,
			"Exclude folders",
			"Folders to exclude from sync (takes precedence over includes).",
			settings.excludeFolders,
			(next) => {
				this.plugin.settings.excludeFolders = next;
			},
		);

		new Setting(containerEl)
			.setName("Advanced exclude patterns")
			.setDesc(
				"Glob fallback for power users. One pattern per line, supports * and **. Lines starting with # are comments. Applied on top of the folder lists above.",
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

		new Setting(containerEl)
			.addButton((btn) =>
				btn
					.setButtonText("View sync status")
					.setCta()
					.onClick(() => this.plugin.openStatusModal()),
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

	private renderFolderList(
		containerEl: HTMLElement,
		title: string,
		desc: string,
		current: string[],
		write: (next: string[]) => void,
	): void {
		const setting = new Setting(containerEl).setName(title).setDesc(desc);

		const persist = async (next: string[]): Promise<void> => {
			const dedup = Array.from(new Set(next.map(normalizeFolder)));
			write(dedup);
			await this.plugin.saveSettings();
			this.display();
		};

		setting.addButton((btn) =>
			btn
				.setButtonText("Add Folder")
				.setCta()
				.onClick(() => {
					new FolderSuggestModal(
						this.app,
						(picked) => {
							void persist([...current, picked]);
						},
						current,
					).open();
				}),
		);

		for (const folder of current) {
			new Setting(containerEl).setName(folder || "/").addExtraButton((btn) =>
				btn
					.setIcon("cross")
					.setTooltip("Remove")
					.onClick(() => {
						void persist(current.filter((f) => f !== folder));
					}),
			);
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
