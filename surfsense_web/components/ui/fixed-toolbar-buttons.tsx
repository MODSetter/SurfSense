"use client";

import {
	BoldIcon,
	Code2Icon,
	HighlighterIcon,
	ItalicIcon,
	RedoIcon,
	SaveIcon,
	StrikethroughIcon,
	UnderlineIcon,
	UndoIcon,
} from "lucide-react";
import { KEYS } from "platejs";
import { useEditorReadOnly, useEditorRef } from "platejs/react";
import * as React from "react";

import { useEditorSave } from "@/components/editor/editor-save-context";
import { Spinner } from "@/components/ui/spinner";
import { usePlatformShortcut } from "@/hooks/use-platform-shortcut";

import { InsertToolbarButton } from "./insert-toolbar-button";
import { LinkToolbarButton } from "./link-toolbar-button";
import { MarkToolbarButton } from "./mark-toolbar-button";
import { ModeToolbarButton } from "./mode-toolbar-button";
import { ToolbarButton, ToolbarGroup } from "./toolbar";
import { TurnIntoToolbarButton } from "./turn-into-toolbar-button";

export function FixedToolbarButtons() {
	const readOnly = useEditorReadOnly();
	const editor = useEditorRef();
	const { onSave, hasUnsavedChanges, isSaving, canToggleMode } = useEditorSave();
	const { shortcut } = usePlatformShortcut();

	return (
		<div className="flex w-full items-center">
			{/* Scrollable editing buttons */}
			<div className="flex flex-1 min-w-0 overflow-x-auto scrollbar-hide">
				{!readOnly && (
					<>
						<ToolbarGroup>
							<ToolbarButton
								tooltip={`Undo ${shortcut("Mod", "Z")}`}
								onClick={() => {
									editor.undo();
									editor.tf.focus();
								}}
							>
								<UndoIcon />
							</ToolbarButton>

							<ToolbarButton
								tooltip={`Redo ${shortcut("Mod", "Shift", "Z")}`}
								onClick={() => {
									editor.redo();
									editor.tf.focus();
								}}
							>
								<RedoIcon />
							</ToolbarButton>
						</ToolbarGroup>

						<ToolbarGroup>
							<InsertToolbarButton />
							<TurnIntoToolbarButton />
						</ToolbarGroup>

						<ToolbarGroup>
							<MarkToolbarButton nodeType={KEYS.bold} tooltip={`Bold ${shortcut("Mod", "B")}`}>
								<BoldIcon />
							</MarkToolbarButton>

							<MarkToolbarButton nodeType={KEYS.italic} tooltip={`Italic ${shortcut("Mod", "I")}`}>
								<ItalicIcon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.underline}
								tooltip={`Underline ${shortcut("Mod", "U")}`}
							>
								<UnderlineIcon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.strikethrough}
								tooltip={`Strikethrough ${shortcut("Mod", "Shift", "X")}`}
							>
								<StrikethroughIcon />
							</MarkToolbarButton>

							<MarkToolbarButton nodeType={KEYS.code} tooltip={`Code ${shortcut("Mod", "E")}`}>
								<Code2Icon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.highlight}
								tooltip={`Highlight ${shortcut("Mod", "Shift", "H")}`}
							>
								<HighlighterIcon />
							</MarkToolbarButton>
						</ToolbarGroup>

						<ToolbarGroup>
							<LinkToolbarButton />
						</ToolbarGroup>
					</>
				)}
			</div>

			{/* Fixed right-side buttons (Save + Mode) */}
			<div className="flex shrink-0 items-center">
				{/* Save button — only in edit mode with unsaved changes */}
				{!readOnly && onSave && hasUnsavedChanges && (
					<ToolbarGroup>
						<ToolbarButton
							tooltip={isSaving ? "Saving..." : `Save ${shortcut("Mod", "S")}`}
							onClick={onSave}
							disabled={isSaving}
							className="bg-primary text-primary-foreground hover:bg-primary/90"
						>
							{isSaving ? <Spinner size="xs" /> : <SaveIcon />}
						</ToolbarButton>
					</ToolbarGroup>
				)}

				{/* Mode toggle */}
				{canToggleMode && (
					<ToolbarGroup>
						<ModeToolbarButton />
					</ToolbarGroup>
				)}
			</div>
		</div>
	);
}
