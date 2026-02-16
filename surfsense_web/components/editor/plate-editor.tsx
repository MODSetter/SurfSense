'use client';

import { useEffect, useRef } from 'react';
import { MarkdownPlugin } from '@platejs/markdown';
import { Plate, usePlateEditor } from 'platejs/react';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';

import { AutoformatKit } from '@/components/editor/plugins/autoformat-classic-kit';
import { BasicNodesKit } from '@/components/editor/plugins/basic-nodes-kit';
import { CalloutKit } from '@/components/editor/plugins/callout-kit';
import { CodeBlockKit } from '@/components/editor/plugins/code-block-kit';
import { FixedToolbarKit } from '@/components/editor/plugins/fixed-toolbar-kit';
import { FloatingToolbarKit } from '@/components/editor/plugins/floating-toolbar-kit';
import { IndentKit } from '@/components/editor/plugins/indent-kit';
import { LinkKit } from '@/components/editor/plugins/link-kit';
import { ListKit } from '@/components/editor/plugins/list-classic-kit';
import { MathKit } from '@/components/editor/plugins/math-kit';
import { SelectionKit } from '@/components/editor/plugins/selection-kit';
import { SlashCommandKit } from '@/components/editor/plugins/slash-command-kit';
import { TableKit } from '@/components/editor/plugins/table-kit';
import { ToggleKit } from '@/components/editor/plugins/toggle-kit';
import { Editor, EditorContainer } from '@/components/ui/editor';

interface PlateEditorProps {
  /** Markdown string to load as initial content */
  markdown?: string;
  /** Called when the editor content changes, with serialized markdown */
  onMarkdownChange?: (markdown: string) => void;
  /** Whether the editor is read-only */
  readOnly?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Editor container variant */
  variant?: 'default' | 'demo' | 'comment' | 'select';
  /** Editor text variant */
  editorVariant?: 'default' | 'demo' | 'fullWidth' | 'none';
  /** Additional className for the container */
  className?: string;
}

export function PlateEditor({
  markdown,
  onMarkdownChange,
  readOnly = false,
  placeholder = 'Type...',
  variant = 'default',
  editorVariant = 'default',
  className,
}: PlateEditorProps) {
  const lastMarkdownRef = useRef(markdown);

  const editor = usePlateEditor({
    plugins: [
      ...BasicNodesKit,
      ...TableKit,
      ...ListKit,
      ...CodeBlockKit,
      ...LinkKit,
      ...CalloutKit,
      ...ToggleKit,
      ...IndentKit,
      ...MathKit,
      ...SelectionKit,
      ...SlashCommandKit,
      ...FixedToolbarKit,
      ...FloatingToolbarKit,
      ...AutoformatKit,
      MarkdownPlugin.configure({
        options: {
          remarkPlugins: [remarkGfm, remarkMath],
        },
      }),
    ],
    // Use markdown deserialization for initial value if provided
    value: markdown
      ? (editor) => editor.getApi(MarkdownPlugin).markdown.deserialize(markdown)
      : undefined,
  });

  // Update editor content when markdown prop changes externally
  // (e.g., version switching in report panel)
  useEffect(() => {
    if (markdown !== undefined && markdown !== lastMarkdownRef.current) {
      lastMarkdownRef.current = markdown;
      const newValue = editor.getApi(MarkdownPlugin).markdown.deserialize(markdown);
      editor.tf.reset();
      editor.tf.setValue(newValue);
    }
  }, [markdown, editor]);

  return (
    <Plate
      editor={editor}
      readOnly={readOnly}
      onChange={({ value }) => {
        if (onMarkdownChange) {
          const md = editor.getApi(MarkdownPlugin).markdown.serialize({ value });
          lastMarkdownRef.current = md;
          onMarkdownChange(md);
        }
      }}
    >
      <EditorContainer variant={variant} className={className}>
        <Editor variant={editorVariant} placeholder={placeholder} readOnly={readOnly} />
      </EditorContainer>
    </Plate>
  );
}
