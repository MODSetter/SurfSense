"use client";

import { MarkdownPlugin, remarkMdx } from "@platejs/markdown";
import { slateToHtml } from "@slate-serializers/html";
import type { AnyPluginConfig, Descendant, Value } from "platejs";
import { createPlatePlugin, Key, Plate, useEditorReadOnly, usePlateEditor } from "platejs/react";
import { useEffect, useMemo, useRef } from "react";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { EditorSaveContext } from "@/components/editor/editor-save-context";
import { CitationKit, injectCitationNodes } from "@/components/editor/plugins/citation-kit";
import { type EditorPreset, presetMap } from "@/components/editor/presets";
import { escapeMdxExpressions } from "@/components/editor/utils/escape-mdx";
import { Editor, EditorContainer } from "@/components/ui/editor";
import { preprocessCitationMarkdown } from "@/lib/citations/citation-parser";

/** Live editor instance returned by `usePlateEditor`. */
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
	 * Render `[citation:N]` and `[citation:URL]` tokens in the deserialized
	 * markdown as interactive citation badges/popovers (mirrors chat). Only
	 * meant for read-only views — when true, `onMarkdownChange` is suppressed
	 * because the in-memory tree contains custom inline-void elements that
	 * have no markdown serialize rule.
	 */
	enableCitations?: boolean;
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
	enableCitations = false,
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
			// Citation void inline element (read-only document viewer).
			...(enableCitations ? CitationKit : []),
			MarkdownPlugin.configure({
				options: {
					remarkPlugins: [remarkGfm, remarkMath, remarkMdx],
				},
			}),
		],
		value: html
			? (editor) => editor.api.html.deserialize({ element: html }) as Value
			: markdown
				? (editor) => {
						if (!enableCitations) {
							return editor
								.getApi(MarkdownPlugin)
								.markdown.deserialize(escapeMdxExpressions(markdown));
						}
						const { content: rewritten, urlMap } = preprocessCitationMarkdown(markdown);
						const value = editor
							.getApi(MarkdownPlugin)
							.markdown.deserialize(escapeMdxExpressions(rewritten));
						return injectCitationNodes(value as Descendant[], urlMap) as Value;
					}
				: undefined,
	});

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
			let newValue: Descendant[];
			if (enableCitations) {
				const { content: rewritten, urlMap } = preprocessCitationMarkdown(markdown);
				const deserialized = editor
					.getApi(MarkdownPlugin)
					.markdown.deserialize(escapeMdxExpressions(rewritten)) as Descendant[];
				newValue = injectCitationNodes(deserialized, urlMap);
			} else {
				newValue = editor
					.getApi(MarkdownPlugin)
					.markdown.deserialize(escapeMdxExpressions(markdown)) as Descendant[];
			}
			editor.tf.reset();
			editor.tf.setValue(newValue as Value);
		}
	}, [html, markdown, editor, enableCitations]);

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
					// View-only citation mode: skip serialization. The custom
					// `citation` inline-void element has no markdown serialize
					// rule, so emitting changes here would overwrite
					// `lastMarkdownRef.current` (and downstream copy-to-clipboard
					// state in EditorPanelContent) with a tree that loses every
					// citation token. `enableCitations` is only ever set in
					// read-only paths, so user input cannot reach this branch
					// in practice — the guard exists for the initial Plate
					// normalize emit.
					if (enableCitations) return;
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
