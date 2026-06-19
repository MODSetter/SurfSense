import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

export interface EditorLineRange {
	start: number;
	end: number;
}

interface EditorPanelState {
	isOpen: boolean;
	kind: "document" | "local_file" | "memory";
	documentId: number | null;
	localFilePath: string | null;
	searchSpaceId: number | null;
	memoryScope: "user" | "team" | null;
	title: string | null;
	// Citation line anchor: when set, the editor opens the raw source view
	// scrolled to and highlighting this 1-based inclusive line range.
	highlightLines: EditorLineRange | null;
	forceSourceView: boolean;
}

const initialState: EditorPanelState = {
	isOpen: false,
	kind: "document",
	documentId: null,
	localFilePath: null,
	searchSpaceId: null,
	memoryScope: null,
	title: null,
	highlightLines: null,
	forceSourceView: false,
};

export const editorPanelAtom = atom<EditorPanelState>(initialState);

export const editorPanelOpenAtom = atom((get) => get(editorPanelAtom).isOpen);

const preEditorCollapsedAtom = atom<boolean | null>(null);

export const openEditorPanelAtom = atom(
	null,
	(
		get,
		set,
		payload:
			| {
					documentId: number;
					searchSpaceId: number;
					title?: string;
					kind?: "document";
					highlightLines?: EditorLineRange | null;
					forceSourceView?: boolean;
			  }
			| {
					kind: "local_file";
					localFilePath: string;
					title?: string;
					searchSpaceId?: number;
			  }
			| {
					kind: "memory";
					memoryScope: "user" | "team";
					title?: string;
					searchSpaceId?: number;
			  }
	) => {
		if (!get(editorPanelAtom).isOpen) {
			set(preEditorCollapsedAtom, get(rightPanelCollapsedAtom));
		}
		if (payload.kind === "local_file") {
			set(editorPanelAtom, {
				isOpen: true,
				kind: "local_file",
				documentId: null,
				localFilePath: payload.localFilePath,
				searchSpaceId: payload.searchSpaceId ?? null,
				memoryScope: null,
				title: payload.title ?? null,
				highlightLines: null,
				forceSourceView: false,
			});
			set(rightPanelTabAtom, "editor");
			set(rightPanelCollapsedAtom, false);
			return;
		}
		if (payload.kind === "memory") {
			set(editorPanelAtom, {
				isOpen: true,
				kind: "memory",
				documentId: null,
				localFilePath: null,
				searchSpaceId: payload.searchSpaceId ?? null,
				memoryScope: payload.memoryScope,
				title: payload.title ?? null,
				highlightLines: null,
				forceSourceView: false,
			});
			set(rightPanelTabAtom, "editor");
			set(rightPanelCollapsedAtom, false);
			return;
		}
		set(editorPanelAtom, {
			isOpen: true,
			kind: "document",
			documentId: payload.documentId,
			localFilePath: null,
			searchSpaceId: payload.searchSpaceId,
			memoryScope: null,
			title: payload.title ?? null,
			highlightLines: payload.highlightLines ?? null,
			forceSourceView: payload.forceSourceView ?? false,
		});
		set(rightPanelTabAtom, "editor");
		set(rightPanelCollapsedAtom, false);
	}
);

export const closeEditorPanelAtom = atom(null, (get, set) => {
	set(editorPanelAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const prev = get(preEditorCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preEditorCollapsedAtom, null);
	}
});
