import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

interface EditorPanelState {
	isOpen: boolean;
	documentId: number | null;
	searchSpaceId: number | null;
	title: string | null;
}

const initialState: EditorPanelState = {
	isOpen: false,
	documentId: null,
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
		{
			documentId,
			searchSpaceId,
			title,
		}: { documentId: number; searchSpaceId: number; title?: string }
	) => {
		if (!get(editorPanelAtom).isOpen) {
			set(preEditorCollapsedAtom, get(rightPanelCollapsedAtom));
		}
		set(editorPanelAtom, {
			isOpen: true,
			documentId,
			searchSpaceId,
			title: title ?? null,
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
