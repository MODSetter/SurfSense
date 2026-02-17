"use client";

import { useEffect, useRef } from "react";
import { MarkdownPlugin, remarkMdx } from "@platejs/markdown";
import { Plate, usePlateEditor } from "platejs/react";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { AutoformatKit } from "@/components/editor/plugins/autoformat-kit";
import { BasicNodesKit } from "@/components/editor/plugins/basic-nodes-kit";
import { CalloutKit } from "@/components/editor/plugins/callout-kit";
import { CodeBlockKit } from "@/components/editor/plugins/code-block-kit";
import { DndKit } from "@/components/editor/plugins/dnd-kit";
import { FixedToolbarKit } from "@/components/editor/plugins/fixed-toolbar-kit";
import { FloatingToolbarKit } from "@/components/editor/plugins/floating-toolbar-kit";
import { LinkKit } from "@/components/editor/plugins/link-kit";
import { ListKit } from "@/components/editor/plugins/list-kit";
import { MathKit } from "@/components/editor/plugins/math-kit";
import { SelectionKit } from "@/components/editor/plugins/selection-kit";
import { SlashCommandKit } from "@/components/editor/plugins/slash-command-kit";
import { TableKit } from "@/components/editor/plugins/table-kit";
import { ToggleKit } from "@/components/editor/plugins/toggle-kit";
import { Editor, EditorContainer } from "@/components/ui/editor";
import { escapeMdxExpressions } from "@/components/editor/utils/escape-mdx";
import { EditorSaveContext } from "@/components/editor/editor-save-context";

interface PlateEditorProps {
	/** Markdown string to load as initial content */
	markdown?: string;
	/** Called when the editor content changes, with serialized markdown */
	onMarkdownChange?: (markdown: string) => void;
	/**
	 * Force permanent read-only mode (e.g. public/shared view).
	 * When true, the editor cannot be toggled to editing mode.
	 * When false (default), the editor starts in viewing mode but
	 * the user can switch to editing via the mode toolbar button.
	 */
	readOnly?: boolean;
	/** Placeholder text */
	placeholder?: string;
	/** Editor container variant */
	variant?: "default" | "demo" | "comment" | "select";
	/** Editor text variant */
	editorVariant?: "default" | "demo" | "fullWidth" | "none";
	/** Additional className for the container */
	className?: string;
	/** Save callback. When provided, a save button appears in the toolbar on unsaved changes. */
	onSave?: () => void;
	/** Whether there are unsaved changes */
	hasUnsavedChanges?: boolean;
	/** Whether a save is in progress */
	isSaving?: boolean;
	/** Start the editor in editing mode instead of viewing mode. Ignored when readOnly is true. */
	defaultEditing?: boolean;
}

export function PlateEditor({
	markdown,
	onMarkdownChange,
	readOnly = false,
	placeholder = "Type...",
	variant = "default",
	editorVariant = "default",
	className,
	onSave,
	hasUnsavedChanges = false,
	isSaving = false,
	defaultEditing = false,
}: PlateEditorProps) {
	const lastMarkdownRef = useRef(markdown);

	// When readOnly is forced, always start in readOnly.
	// Otherwise, respect defaultEditing to decide initial mode.
	// The user can still toggle between editing/viewing via ModeToolbarButton.
	const editor = usePlateEditor({
		readOnly: readOnly || !defaultEditing,
		plugins: [
			...BasicNodesKit,
			...TableKit,
			...ListKit,
			...CodeBlockKit,
			...LinkKit,
			...CalloutKit,
			...ToggleKit,
			...MathKit,
			...SelectionKit,
			...SlashCommandKit,
			...FixedToolbarKit,
			...FloatingToolbarKit,
			...AutoformatKit,
			...DndKit,
			MarkdownPlugin.configure({
				options: {
					remarkPlugins: [remarkGfm, remarkMath, remarkMdx],
				},
			}),
		],
		// Use markdown deserialization for initial value if provided
		value: markdown
			? (editor) =>
					editor.getApi(MarkdownPlugin).markdown.deserialize(escapeMdxExpressions(markdown))
			: undefined,
	});

	// Update editor content when markdown prop changes externally
	// (e.g., version switching in report panel)
	useEffect(() => {
		if (markdown !== undefined && markdown !== lastMarkdownRef.current) {
			lastMarkdownRef.current = markdown;
			const newValue = editor
				.getApi(MarkdownPlugin)
				.markdown.deserialize(escapeMdxExpressions(markdown));
			editor.tf.reset();
			editor.tf.setValue(newValue);
		}
	}, [markdown, editor]);

	// When not forced read-only, the user can toggle between editing/viewing.
	const canToggleMode = !readOnly;

	return (
		<EditorSaveContext.Provider
			value={{
				onSave,
				hasUnsavedChanges,
				isSaving,
				canToggleMode,
			}}
		>
			<Plate
				editor={editor}
				// Only pass readOnly as a controlled prop when forced (permanently read-only).
				// For non-forced mode, the Plate store manages readOnly internally
				// (initialized to true via usePlateEditor, toggled via ModeToolbarButton).
				{...(readOnly ? { readOnly: true } : {})}
				onChange={({ value }) => {
					if (onMarkdownChange) {
						const md = editor.getApi(MarkdownPlugin).markdown.serialize({ value });
						lastMarkdownRef.current = md;
						onMarkdownChange(md);
					}
				}}
			>
				<EditorContainer variant={variant} className={className}>
					<Editor variant={editorVariant} placeholder={placeholder} />
				</EditorContainer>
			</Plate>
		</EditorSaveContext.Provider>
	);
}
