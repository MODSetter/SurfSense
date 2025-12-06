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
}

export default function BlockNoteEditor({ initialContent, onChange }: BlockNoteEditorProps) {
	const { resolvedTheme } = useTheme();

	// Track the initial content to prevent re-initialization
	const initialContentRef = useRef<any>(null);
	const isInitializedRef = useRef(false);

	// Creates a new editor instance - only use initialContent on first render
	const editor = useCreateBlockNote({
		initialContent: initialContentRef.current === null ? initialContent || undefined : undefined,
	});

	// Store initial content on first render only
	useEffect(() => {
		if (initialContent && initialContentRef.current === null) {
			initialContentRef.current = initialContent;
			isInitializedRef.current = true;
		}
	}, [initialContent]);

	// Call onChange when document changes (but don't update from props)
	useEffect(() => {
		if (!onChange || !editor || !isInitializedRef.current) return;

		const handleChange = () => {
			onChange(editor.document);
		};

		// Subscribe to document changes
		const unsubscribe = editor.onChange(handleChange);

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
	return <BlockNoteView editor={editor} theme={blockNoteTheme} />;
}
