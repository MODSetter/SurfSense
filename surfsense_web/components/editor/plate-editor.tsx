"use client";

import { MarkdownPlugin, remarkMdx } from "@platejs/markdown";
import { slateToHtml } from "@slate-serializers/html";
import type { AnyPluginConfig, Descendant, Value } from "platejs";
import { createPlatePlugin, Key, Plate, useEditorReadOnly, usePlateEditor } from "platejs/react";
import { useEffect, useMemo, useRef } from "react";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { EditorSaveContext } from "@/components/editor/editor-save-context";
import { type EditorPreset, presetMap } from "@/components/editor/presets";
import { escapeMdxExpressions } from "@/components/editor/utils/escape-mdx";
import { Editor, EditorContainer } from "@/components/ui/editor";

/** Live editor instance returned by `usePlateEditor`. Exposed via the
 * `onEditorReady` prop so callers (e.g. `EditorPanelContent`) can drive
 * plugin options imperatively — most notably setting
 * `FindReplacePlugin`'s `search` option for citation-jump highlights. */
export type PlateEditorInstance = ReturnType<typeof usePlateEditor>;

export interface PlateEditorProps {
	/** Markdown string to load as initial content */
	markdown?: string;
	/** HTML string to load as initial content. Takes precedence over `markdown`. */
	html?: string;
	/** Called when the editor content changes, with serialized markdown */
	onMarkdownChange?: (markdown: string) => void;
	/** Called when the editor content changes, with serialized HTML. Use with the `html` prop. */
	onHtmlChange?: (html: string) => void;
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
	/** Whether edit/view mode toggle UI should be available in toolbars. */
	allowModeToggle?: boolean;
	/** Reserve fixed-toolbar vertical space even when controls are hidden. */
	reserveToolbarSpace?: boolean;
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
	/**
	 * Called whenever the live editor instance (re)mounts, with `null` on
	 * unmount. Used by callers that need to drive plugin options imperatively
	 * — e.g. `EditorPanelContent` setting `FindReplacePlugin`'s `search`
	 * option for citation-jump highlights. The callback is invoked exactly
	 * once per editor lifetime (the parent's `key` prop forces a fresh
	 * editor when needed, e.g. on edit-mode toggle).
	 */
	onEditorReady?: (editor: PlateEditorInstance | null) => void;
}

function PlateEditorContent({
	editorVariant,
	placeholder,
}: {
	editorVariant: PlateEditorProps["editorVariant"];
	placeholder?: string;
}) {
	const isReadOnly = useEditorReadOnly();

	return (
		<Editor
			variant={editorVariant}
			placeholder={isReadOnly ? undefined : placeholder}
			className="min-h-full"
		/>
	);
}

export function PlateEditor({
	markdown,
	html,
	onMarkdownChange,
	onHtmlChange,
	readOnly = false,
	placeholder = "Type...",
	variant = "default",
	editorVariant = "default",
	className,
	onSave,
	hasUnsavedChanges = false,
	isSaving = false,
	allowModeToggle = true,
	reserveToolbarSpace = false,
	defaultEditing = false,
	preset = "full",
	extraPlugins = [],
	onEditorReady,
}: PlateEditorProps) {
	const lastMarkdownRef = useRef(markdown);
	const lastHtmlRef = useRef(html);

	// Keep a stable ref to the latest onSave callback so the plugin shortcut
	// always calls the most recent version without re-creating the editor.
	const onSaveRef = useRef(onSave);
	useEffect(() => {
		onSaveRef.current = onSave;
	}, [onSave]);

	const SaveShortcutPlugin = useMemo(
		() =>
			createPlatePlugin({
				key: "save-shortcut",
				shortcuts: {
					save: {
						keys: [[Key.Mod, Key.Shift, "s"]],
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
		value: html
			? (editor) => editor.api.html.deserialize({ element: html }) as Value
			: markdown
				? (editor) =>
						editor.getApi(MarkdownPlugin).markdown.deserialize(escapeMdxExpressions(markdown))
				: undefined,
	});

	// Expose the live editor instance to imperative callers (e.g. citation
	// jump highlights). We deliberately don't depend on `onEditorReady`
	// itself in the cleanup closure — callers commonly pass an arrow that
	// closes over a stable ref setter, but if they pass a freshly-bound
	// callback per render, the `onEditorReady?.(editor)` re-fires which is
	// idempotent for ref-style setters.
	const onEditorReadyRef = useRef(onEditorReady);
	useEffect(() => {
		onEditorReadyRef.current = onEditorReady;
	}, [onEditorReady]);
	useEffect(() => {
		onEditorReadyRef.current?.(editor);
		return () => onEditorReadyRef.current?.(null);
	}, [editor]);

	// Update editor content when html prop changes externally
	useEffect(() => {
		if (html !== undefined && html !== lastHtmlRef.current) {
			lastHtmlRef.current = html;
			const newValue = editor.api.html.deserialize({ element: html });
			editor.tf.reset();
			editor.tf.setValue(newValue);
		}
	}, [html, editor]);

	// Update editor content when markdown prop changes externally
	// (e.g., version switching in report panel)
	useEffect(() => {
		if (!html && markdown !== undefined && markdown !== lastMarkdownRef.current) {
			lastMarkdownRef.current = markdown;
			const newValue = editor
				.getApi(MarkdownPlugin)
				.markdown.deserialize(escapeMdxExpressions(markdown));
			editor.tf.reset();
			editor.tf.setValue(newValue);
		}
	}, [html, markdown, editor]);

	// When not forced read-only, the user can toggle between editing/viewing.
	const canToggleMode = !readOnly && allowModeToggle;

	const contextProviderValue = useMemo(
		() => ({
			onSave,
			hasUnsavedChanges,
			isSaving,
			canToggleMode,
			reserveToolbarSpace,
		}),
		[onSave, hasUnsavedChanges, isSaving, canToggleMode, reserveToolbarSpace]
	);

	return (
		<EditorSaveContext.Provider value={contextProviderValue}>
			<Plate
				editor={editor}
				// Only pass readOnly as a controlled prop when forced (permanently read-only).
				// For non-forced mode, the Plate store manages readOnly internally
				// (initialized to true via usePlateEditor, toggled via ModeToolbarButton).
				{...(readOnly ? { readOnly: true } : {})}
				onChange={({ value }) => {
					if (onHtmlChange && html) {
						const serialized = slateToHtml(value as Descendant[]);
						onHtmlChange(serialized);
					} else if (onMarkdownChange) {
						const md = editor.getApi(MarkdownPlugin).markdown.serialize({ value });
						lastMarkdownRef.current = md;
						onMarkdownChange(md);
					}
				}}
			>
				<EditorContainer variant={variant} className={className}>
					<PlateEditorContent editorVariant={editorVariant} placeholder={placeholder} />
				</EditorContainer>
			</Plate>
		</EditorSaveContext.Provider>
	);
}
