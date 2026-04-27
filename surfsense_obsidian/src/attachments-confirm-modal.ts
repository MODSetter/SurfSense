import { type App, Modal, Setting } from "obsidian";

/**
 * Confirmation modal shown before enabling attachment sync.
 * Attachment files can be large and increase sync latency/cost.
 */
export class AttachmentsConfirmModal extends Modal {
	private resolver: ((confirmed: boolean) => void) | null = null;

	constructor(app: App) {
		super(app);
	}

	onOpen(): void {
		this.setTitle("Enable attachment sync?");
		this.contentEl.empty();

		new Setting(this.contentEl).setDesc(
			"Syncing attachments (images & PDFs) can make indexing slower, especially on large vaults."
		);
		new Setting(this.contentEl).setDesc(
			"Syncing attachments can make indexing slower on large vaults. You can disable this anytime.",
		);

		new Setting(this.contentEl)
			.addButton((btn) =>
				btn
					.setButtonText("Cancel")
					.onClick(() => this.resolveAndClose(false)),
			)
			.addButton((btn) =>
				btn
					.setButtonText("Enable")
					.setCta()
					.onClick(() => this.resolveAndClose(true)),
			);
	}

	onClose(): void {
		this.contentEl.empty();
		if (this.resolver) {
			this.resolver(false);
			this.resolver = null;
		}
	}

	waitForConfirmation(): Promise<boolean> {
		this.open();
		return new Promise<boolean>((resolve) => {
			this.resolver = resolve;
		});
	}

	private resolveAndClose(confirmed: boolean): void {
		if (this.resolver) {
			this.resolver(confirmed);
			this.resolver = null;
		}
		this.close();
	}
}
