"use client";

import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef } from "react";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";
import { BlockNoteView } from "@blocknote/mantine";
import { useCreateBlockNote } from "@blocknote/react";

interface BlockNoteEditorProps {
	initialContent?: any;
	onChange?: (content: any) => void;
	useTitleBlock?: boolean; // Whether to use first block as title (Notion-style)
}

// Helper to ensure first block is a heading for title
function ensureTitleBlock(content: any[] | undefined): any[] {
	if (!content || content.length === 0) {
		// Return empty heading block for new notes
		return [
			{
				type: "heading",
				props: { level: 1 },
				content: [],
				children: [],
			},
		];
	}

	// If first block is not a heading, convert it to one
	const firstBlock = content[0];
	if (firstBlock?.type !== "heading") {
		// Extract text from first block
		let titleText = "";
		if (firstBlock?.content && Array.isArray(firstBlock.content)) {
			titleText = firstBlock.content
				.map((item: any) => {
					if (typeof item === "string") return item;
					if (item?.text) return item.text;
					return "";
				})
				.join("")
				.trim();
		}

		// Create heading block with extracted text
		const titleBlock = {
			type: "heading",
			props: { level: 1 },
			content: titleText
				? [
						{
							type: "text",
							text: titleText,
							styles: {},
						},
					]
				: [],
			children: [],
		};

		// Replace first block with heading, keep rest
		return [titleBlock, ...content.slice(1)];
	}

	return content;
}

export default function BlockNoteEditor({
	initialContent,
	onChange,
	useTitleBlock = false,
}: BlockNoteEditorProps) {
	const { resolvedTheme } = useTheme();

	// Track the initial content to prevent re-initialization
	const initialContentRef = useRef<any>(null);
	const isInitializedRef = useRef(false);

	// Prepare initial content - ensure first block is a heading if useTitleBlock is true
	const preparedInitialContent = useMemo(() => {
		if (initialContentRef.current !== null) {
			return undefined; // Already initialized
		}
		if (initialContent === undefined) {
			// New note - create empty heading block
			return useTitleBlock
				? [
						{
							type: "heading",
							props: { level: 1 },
							content: [],
							children: [],
						},
					]
				: undefined;
		}
		// Existing note - ensure first block is heading
		return useTitleBlock ? ensureTitleBlock(initialContent) : initialContent;
	}, [initialContent, useTitleBlock]);

	// Creates a new editor instance - only use initialContent on first render
	const editor = useCreateBlockNote({
		initialContent: initialContentRef.current === null ? preparedInitialContent : undefined,
	});

	// Store initial content on first render only
	useEffect(() => {
		if (preparedInitialContent !== undefined && initialContentRef.current === null) {
			initialContentRef.current = preparedInitialContent;
			isInitializedRef.current = true;
		} else if (preparedInitialContent === undefined && initialContentRef.current === null) {
			// Mark as initialized even when initialContent is undefined (for new notes)
			isInitializedRef.current = true;
		}
	}, [preparedInitialContent]);

	// Call onChange when document changes (but don't update from props)
	useEffect(() => {
		if (!onChange || !editor) return;

		// For new notes (no initialContent), we need to wait for editor to be ready
		// Use a small delay to ensure editor is fully initialized
		if (!isInitializedRef.current) {
			const timer = setTimeout(() => {
				isInitializedRef.current = true;
			}, 100);
			return () => clearTimeout(timer);
		}

		const handleChange = () => {
			onChange(editor.document);
		};

		// Subscribe to document changes
		const unsubscribe = editor.onChange(handleChange);

		// Also call onChange once with current document to capture initial state
		// This ensures we capture content even if user doesn't make changes
		if (editor.document) {
			onChange(editor.document);
		}

		return () => {
			unsubscribe();
		};
	}, [editor, onChange]);

	// Determine theme for BlockNote with custom dark mode background
	const blockNoteTheme = useMemo(() => {
		if (resolvedTheme === "dark") {
			// Custom dark theme - only override editor background, let BlockNote handle the rest
			return {
				colors: {
					editor: {
						background: "#0A0A0A", // Custom dark background
					},
				},
			};
		}
		return "light" as const;
	}, [resolvedTheme]);

	// Renders the editor instance
	return (
		<div className="bn-container">
			<style>{`
				@media (max-width: 640px) {
					.bn-container .bn-editor {
						padding-inline: 12px !important;
					}

					/* Heading Level 1 (Title) */
					.bn-container [data-content-type="heading"][data-level="1"] {
						font-size: 1.75rem !important;
						line-height: 1.2 !important;
						margin-top: 1rem !important;
						margin-bottom: 0.5rem !important;
					}

					/* Heading Level 2 */
					.bn-container [data-content-type="heading"][data-level="2"] {
						font-size: 1.5rem !important;
						line-height: 1.2 !important;
						margin-top: 0.875rem !important;
						margin-bottom: 0.375rem !important;
					}

					/* Heading Level 3 */
					.bn-container [data-content-type="heading"][data-level="3"] {
						font-size: 1.25rem !important;
						line-height: 1.2 !important;
						margin-top: 0.75rem !important;
						margin-bottom: 0.25rem !important;
					}

					/* Paragraphs and regular content */
					.bn-container .bn-block-content {
						font-size: 0.9375rem !important;
						line-height: 1.5 !important;
					}

					/* Adjust lists */
					.bn-container ul,
					.bn-container ol {
						padding-left: 1.25rem !important;
					}
				}
			`}</style>
			<BlockNoteView editor={editor} theme={blockNoteTheme} />
		</div>
	);
}
