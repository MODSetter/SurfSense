import { type App, Modal, Notice, Setting } from "obsidian";
import type SurfSensePlugin from "./main";

/**
 * Read-only status panel. Mirrors what the settings tab used to embed inline,
 * but as a modal so it's reachable from the status bar / command palette.
 *
 * Subscribes to plugin status changes while open so the numbers stay live;
 * unsubscribes on close.
 */
export class StatusModal extends Modal {
	private readonly plugin: SurfSensePlugin;
	private readonly onChange = (): void => this.render();

	constructor(app: App, plugin: SurfSensePlugin) {
		super(app);
		this.plugin = plugin;
	}

	onOpen(): void {
		this.titleEl.setText("SurfSense status");
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
							new Notice("SurfSense: re-sync requested.");
						} catch (err) {
							new Notice(
								`SurfSense: re-sync failed — ${(err as Error).message}`,
							);
						} finally {
							btn.setDisabled(false);
						}
					}),
			)
			.addButton((btn) => btn.setButtonText("Close").onClick(() => this.close()));
	}
}
