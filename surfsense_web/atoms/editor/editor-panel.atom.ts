import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

interface EditorPanelState {
	isOpen: boolean;
	kind: "document" | "local_file" | "memory";
	documentId: number | null;
	localFilePath: string | null;
	workspaceId: number | null;
	memoryScope: "user" | "team" | null;
	title: string | null;
}

const initialState: EditorPanelState = {
	isOpen: false,
	kind: "document",
	documentId: null,
	localFilePath: null,
	workspaceId: null,
	memoryScope: null,
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
			| { documentId: number; workspaceId: number; title?: string; kind?: "document" }
			| {
					kind: "local_file";
					localFilePath: string;
					title?: string;
					workspaceId?: number;
			  }
			| {
					kind: "memory";
					memoryScope: "user" | "team";
					title?: string;
					workspaceId?: number;
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
				workspaceId: payload.workspaceId ?? null,
				memoryScope: null,
				title: payload.title ?? null,
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
				workspaceId: payload.workspaceId ?? null,
				memoryScope: payload.memoryScope,
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
			workspaceId: payload.workspaceId,
			memoryScope: null,
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
