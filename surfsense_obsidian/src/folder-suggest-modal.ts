import { type App, FuzzySuggestModal, type TFolder } from "obsidian";

/** Folder picker built on Obsidian's stock {@link FuzzySuggestModal}. */
export class FolderSuggestModal extends FuzzySuggestModal<TFolder> {
	private readonly onPick: (path: string) => void;
	private readonly excluded: Set<string>;

	constructor(app: App, onPick: (path: string) => void, excluded: string[] = []) {
		super(app);
		this.onPick = onPick;
		this.excluded = new Set(excluded.map((p) => p.replace(/^\/+|\/+$/g, "")));
		this.setPlaceholder("Type to filter folders…");
	}

	getItems(): TFolder[] {
		return this.app.vault
			.getAllFolders(true)
			.filter((f) => !this.excluded.has(this.toPath(f)));
	}

	getItemText(folder: TFolder): string {
		return this.toPath(folder) || "/";
	}

	onChooseItem(folder: TFolder): void {
		this.onPick(this.toPath(folder));
	}

	private toPath(folder: TFolder): string {
		return folder.isRoot() ? "" : folder.path;
	}
}
