"use client";

import { createPlatePlugin } from "platejs/react";
import { useEditorReadOnly } from "platejs/react";

import { useEditorSave } from "@/components/editor/editor-save-context";
import { FixedToolbar } from "@/components/ui/fixed-toolbar";
import { FixedToolbarButtons } from "@/components/ui/fixed-toolbar-buttons";

function ConditionalFixedToolbar() {
	const readOnly = useEditorReadOnly();
	const { onSave, hasUnsavedChanges, canToggleMode, reserveToolbarSpace } = useEditorSave();

	const hasVisibleControls =
		!readOnly || canToggleMode || (!!onSave && hasUnsavedChanges && !readOnly);

	if (!hasVisibleControls) {
		if (!reserveToolbarSpace) return null;
		return (
			<FixedToolbar className="pointer-events-none opacity-0">
				<div className="h-8 w-full" />
			</FixedToolbar>
		);
	}

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
