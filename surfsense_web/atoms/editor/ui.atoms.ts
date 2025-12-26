import { atom } from "jotai";

interface EditorUIState {
	hasUnsavedChanges: boolean;
	pendingNavigation: string | null; // URL to navigate to after user confirms
}

export const editorUIAtom = atom<EditorUIState>({
	hasUnsavedChanges: false,
	pendingNavigation: null,
});

// Derived atom for just the unsaved changes state
export const hasUnsavedEditorChangesAtom = atom(
	(get) => get(editorUIAtom).hasUnsavedChanges,
	(get, set, value: boolean) => {
		set(editorUIAtom, { ...get(editorUIAtom), hasUnsavedChanges: value });
	}
);

// Derived atom for pending navigation
export const pendingEditorNavigationAtom = atom(
	(get) => get(editorUIAtom).pendingNavigation,
	(get, set, value: string | null) => {
		set(editorUIAtom, { ...get(editorUIAtom), pendingNavigation: value });
	}
);
