"use client";

import { MarkdownPlugin, remarkMdx } from "@platejs/markdown";
import type { AnyPluginConfig } from "platejs";
import { createPlatePlugin, Key, Plate, usePlateEditor } from "platejs/react";
import { useEffect, useMemo, useRef } from "react";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { EditorSaveContext } from "@/components/editor/editor-save-context";
import { type EditorPreset, presetMap } from "@/components/editor/presets";
import { escapeMdxExpressions } from "@/components/editor/utils/escape-mdx";
import { Editor, EditorContainer } from "@/components/ui/editor";

export interface PlateEditorProps {
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
	/** Save callback. When provided, ⌘+S / Ctrl+S shortcut is registered and save button appears. */
	onSave?: () => void;
	/** Whether there are unsaved changes */
	hasUnsavedChanges?: boolean;
	/** Whether a save is in progress */
	isSaving?: boolean;
	/** Start the editor in editing mode instead of viewing mode. Ignored when readOnly is true. */
	defaultEditing?: boolean;
	/**
	 * Plugin preset to use. Controls which plugin kits are loaded.
	 * - "full"     – all plugins (toolbars, slash commands, DnD, etc.)
	 * - "minimal"  – core formatting only (no fixed toolbar, slash commands, DnD, block selection)
	 * - "readonly" – rendering support for all rich content, no editing UI
	 * @default "full"
	 */
	preset?: EditorPreset;
	/**
	 * Additional plugins to append after the preset plugins.
	 * Use this to inject feature-specific plugins (e.g. approve/reject blocks)
	 * without modifying the core editor component.
	 */
	extraPlugins?: AnyPluginConfig[];
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
	preset = "full",
	extraPlugins = [],
}: PlateEditorProps) {
	const lastMarkdownRef = useRef(markdown);

	// Keep a stable ref to the latest onSave callback so the plugin shortcut
	// always calls the most recent version without re-creating the editor.
	const onSaveRef = useRef(onSave);
	useEffect(() => {
		onSaveRef.current = onSave;
	}, [onSave]);

	// Stable Plate plugin for ⌘+S / Ctrl+S save shortcut.
	// Only included when onSave is provided.
	const SaveShortcutPlugin = useMemo(
		() =>
			createPlatePlugin({
				key: "save-shortcut",
				shortcuts: {
					save: {
						keys: [[Key.Mod, "s"]],
						handler: () => {
							onSaveRef.current?.();
						},
						preventDefault: true,
					},
				},
			}),
		[]
	);

	// Resolve the plugin set from the chosen preset
	const presetPlugins = presetMap[preset];

	// When readOnly is forced, always start in readOnly.
	// Otherwise, respect defaultEditing to decide initial mode.
	// The user can still toggle between editing/viewing via ModeToolbarButton.
	const editor = usePlateEditor({
		readOnly: readOnly || !defaultEditing,
		plugins: [
			...presetPlugins,
			// Only register save shortcut when a save handler is provided
			...(onSave ? [SaveShortcutPlugin] : []),
			// Consumer-provided extra plugins
			...extraPlugins,
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
