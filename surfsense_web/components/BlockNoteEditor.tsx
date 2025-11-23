"use client";

import { useEffect, useRef } from "react";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";

interface BlockNoteEditorProps {
  initialContent?: any;
  onChange?: (content: any) => void;
}

export default function BlockNoteEditor({
  initialContent,
  onChange,
}: BlockNoteEditorProps) {
  // Track the initial content to prevent re-initialization
  const initialContentRef = useRef<any>(null);
  const isInitializedRef = useRef(false);
  
  // Creates a new editor instance - only use initialContent on first render
  const editor = useCreateBlockNote({
    initialContent: initialContentRef.current === null ? (initialContent || undefined) : undefined,
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

  // Renders the editor instance
  return <BlockNoteView editor={editor} />;
}
