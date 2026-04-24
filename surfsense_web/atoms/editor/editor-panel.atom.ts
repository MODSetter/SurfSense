import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

interface EditorPanelState {
	isOpen: boolean;
	kind: "document" | "local_file";
	documentId: number | null;
	localFilePath: string | null;
	searchSpaceId: number | null;
	title: string | null;
}

const initialState: EditorPanelState = {
	isOpen: false,
	kind: "document",
	documentId: null,
	localFilePath: null,
	searchSpaceId: null,
	title: null,
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
			| { documentId: number; searchSpaceId: number; title?: string; kind?: "document" }
			| {
					kind: "local_file";
					localFilePath: string;
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
				title: payload.title ?? null,
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
			title: payload.title ?? null,
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
