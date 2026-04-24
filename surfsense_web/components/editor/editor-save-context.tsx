"use client";

import { createContext, useContext } from "react";

interface EditorSaveContextValue {
	/** Callback to save the current editor content */
	onSave?: () => void;
	/** Whether there are unsaved changes */
	hasUnsavedChanges: boolean;
	/** Whether a save operation is in progress */
	isSaving: boolean;
	/** Whether the user can toggle between editing and viewing modes */
	canToggleMode: boolean;
	/** Whether fixed-toolbar space should be reserved even when controls are hidden */
	reserveToolbarSpace: boolean;
}

export const EditorSaveContext = createContext<EditorSaveContextValue>({
	hasUnsavedChanges: false,
	isSaving: false,
	canToggleMode: false,
	reserveToolbarSpace: false,
});

export function useEditorSave() {
	return useContext(EditorSaveContext);
}
