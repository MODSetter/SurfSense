import { type App, Modal, Notice, Setting } from "obsidian";
import type SurfSensePlugin from "./main";

/** Live status panel reachable from the status bar / command palette. */
export class StatusModal extends Modal {
	private readonly plugin: SurfSensePlugin;
	private readonly onChange = (): void => this.render();

	constructor(app: App, plugin: SurfSensePlugin) {
		super(app);
		this.plugin = plugin;
	}

	onOpen(): void {
		this.setTitle("Surfsense status");
		this.plugin.onStatusChange(this.onChange);
		this.render();
	}

	onClose(): void {
		this.plugin.offStatusChange(this.onChange);
		this.contentEl.empty();
	}

	private render(): void {
		const { contentEl, plugin } = this;
		contentEl.empty();
		const s = plugin.settings;

		const rows: Array<[string, string]> = [
			["Status", plugin.lastStatus.kind],
			[
				"Last sync",
				s.lastSyncAt ? new Date(s.lastSyncAt).toLocaleString() : "—",
			],
			[
				"Last reconcile",
				s.lastReconcileAt
					? new Date(s.lastReconcileAt).toLocaleString()
					: "—",
			],
			["Files synced", String(s.filesSynced ?? 0)],
			["Queue depth", String(plugin.queueDepth)],
			[
				"Capabilities",
				plugin.serverCapabilities.length
					? plugin.serverCapabilities.join(", ")
					: "(not yet handshaken)",
			],
		];
		for (const [label, value] of rows) {
			new Setting(contentEl).setName(label).setDesc(value);
		}

		new Setting(contentEl)
			.addButton((btn) =>
				btn
					.setButtonText("Re-sync entire vault")
					.setCta()
					.onClick(async () => {
						btn.setDisabled(true);
						try {
							await plugin.engine.maybeReconcile(true);
							new Notice("Surfsense: re-sync requested.");
						} catch (err) {
							new Notice(
								`Surfsense: re-sync failed — ${(err as Error).message}`,
							);
						} finally {
							btn.setDisabled(false);
						}
					}),
			)
			.addButton((btn) => btn.setButtonText("Close").onClick(() => this.close()));
	}
}
