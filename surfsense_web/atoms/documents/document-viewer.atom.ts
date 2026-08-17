import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

interface DocumentViewerState {
	isOpen: boolean;
	documentId: number | null;
	workspaceId: number | null;
	title: string;
}

const initialState: DocumentViewerState = {
	isOpen: false,
	documentId: null,
	workspaceId: null,
	title: "",
};

export const documentViewerAtom = atom<DocumentViewerState>(initialState);
const previousCollapsedAtom = atom<boolean | null>(null);

export const openDocumentViewerAtom = atom(
	null,
	(
		get,
		set,
		{
			documentId,
			workspaceId,
			title,
		}: { documentId: number; workspaceId: number; title: string }
	) => {
		if (!get(documentViewerAtom).isOpen) {
			set(previousCollapsedAtom, get(rightPanelCollapsedAtom));
		}
		set(documentViewerAtom, { isOpen: true, documentId, workspaceId, title });
		set(rightPanelTabAtom, "document");
		set(rightPanelCollapsedAtom, false);
	}
);

export const closeDocumentViewerAtom = atom(null, (get, set) => {
	set(documentViewerAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const previous = get(previousCollapsedAtom);
	if (previous !== null) {
		set(rightPanelCollapsedAtom, previous);
		set(previousCollapsedAtom, null);
	}
});
