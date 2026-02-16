'use client';

import * as React from 'react';

import {
  BoldIcon,
  Code2Icon,
  HighlighterIcon,
  ItalicIcon,
  RedoIcon,
  StrikethroughIcon,
  UnderlineIcon,
  UndoIcon,
} from 'lucide-react';
import { KEYS } from 'platejs';
import { useEditorReadOnly, useEditorRef } from 'platejs/react';

import { InsertToolbarButton } from './insert-toolbar-button';
import { LinkToolbarButton } from './link-toolbar-button';
import { MarkToolbarButton } from './mark-toolbar-button';
import { MoreToolbarButton } from './more-toolbar-button';
import { ToolbarButton, ToolbarGroup } from './toolbar';
import { TurnIntoToolbarButton } from './turn-into-toolbar-button';

export function FixedToolbarButtons() {
  const readOnly = useEditorReadOnly();
  const editor = useEditorRef();

  if (readOnly) return null;

  return (
    <div className="flex w-full flex-wrap">
      <ToolbarGroup>
        <ToolbarButton
          tooltip="Undo (⌘+Z)"
          onClick={() => {
            editor.undo();
            editor.tf.focus();
          }}
        >
          <UndoIcon />
        </ToolbarButton>

        <ToolbarButton
          tooltip="Redo (⌘+⇧+Z)"
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
        <MarkToolbarButton nodeType={KEYS.bold} tooltip="Bold (⌘+B)">
          <BoldIcon />
        </MarkToolbarButton>

        <MarkToolbarButton nodeType={KEYS.italic} tooltip="Italic (⌘+I)">
          <ItalicIcon />
        </MarkToolbarButton>

        <MarkToolbarButton
          nodeType={KEYS.underline}
          tooltip="Underline (⌘+U)"
        >
          <UnderlineIcon />
        </MarkToolbarButton>

        <MarkToolbarButton
          nodeType={KEYS.strikethrough}
          tooltip="Strikethrough (⌘+⇧+M)"
        >
          <StrikethroughIcon />
        </MarkToolbarButton>

        <MarkToolbarButton nodeType={KEYS.code} tooltip="Code (⌘+E)">
          <Code2Icon />
        </MarkToolbarButton>

        <MarkToolbarButton
          nodeType={KEYS.highlight}
          tooltip="Highlight (⌘+⇧+H)"
        >
          <HighlighterIcon />
        </MarkToolbarButton>
      </ToolbarGroup>

      <ToolbarGroup>
        <LinkToolbarButton />
      </ToolbarGroup>

      <ToolbarGroup>
        <MoreToolbarButton />
      </ToolbarGroup>
    </div>
  );
}

