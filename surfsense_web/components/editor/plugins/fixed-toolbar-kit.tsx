"use client";

import { createPlatePlugin } from "platejs/react";
import { useEditorReadOnly } from "platejs/react";

import { useEditorSave } from "@/components/editor/editor-save-context";
import { FixedToolbar } from "@/components/ui/fixed-toolbar";
import { FixedToolbarButtons } from "@/components/ui/fixed-toolbar-buttons";

function ConditionalFixedToolbar() {
	const readOnly = useEditorReadOnly();
	const { onSave, hasUnsavedChanges, canToggleMode } = useEditorSave();

	const hasVisibleControls =
		!readOnly || canToggleMode || (!!onSave && hasUnsavedChanges && !readOnly);

	if (!hasVisibleControls) return null;

	return (
		<FixedToolbar>
			<FixedToolbarButtons />
		</FixedToolbar>
	);
}

export const FixedToolbarKit = [
	createPlatePlugin({
		key: "fixed-toolbar",
		render: {
			beforeEditable: () => <ConditionalFixedToolbar />,
		},
	}),
];
