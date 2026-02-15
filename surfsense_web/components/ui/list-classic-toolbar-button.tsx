'use client';

import * as React from 'react';

import { indentListItems, unindentListItems } from '@platejs/list-classic';
import {
  useListToolbarButton,
  useListToolbarButtonState,
} from '@platejs/list-classic/react';
import {
  IndentIcon,
  List,
  ListOrdered,
  ListTodo,
  OutdentIcon,
} from 'lucide-react';
import { KEYS } from 'platejs';
import { useEditorRef } from 'platejs/react';

import { ToolbarButton } from './toolbar';

const nodeTypeMap: Record<string, { icon: React.JSX.Element; label: string }> =
  {
    [KEYS.olClassic]: { icon: <ListOrdered />, label: 'Numbered List' },
    [KEYS.taskList]: { icon: <ListTodo />, label: 'Task List' },
    [KEYS.ulClassic]: { icon: <List />, label: 'Bulleted List' },
  };

export function ListToolbarButton({
  nodeType = KEYS.ulClassic,
  ...props
}: React.ComponentProps<typeof ToolbarButton> & {
  nodeType?: string;
}) {
  const state = useListToolbarButtonState({ nodeType });
  const { props: buttonProps } = useListToolbarButton(state);
  const { icon, label } = nodeTypeMap[nodeType] ?? nodeTypeMap[KEYS.ulClassic];

  return (
    <ToolbarButton {...props} {...buttonProps} tooltip={label}>
      {icon}
    </ToolbarButton>
  );
}

export function IndentToolbarButton({
  reverse = false,
  ...props
}: React.ComponentProps<typeof ToolbarButton> & {
  reverse?: boolean;
}) {
  const editor = useEditorRef();

  return (
    <ToolbarButton
      {...props}
      onClick={() => {
        if (reverse) {
          unindentListItems(editor);
        } else {
          indentListItems(editor);
        }
      }}
      tooltip={reverse ? 'Outdent' : 'Indent'}
    >
      {reverse ? <OutdentIcon /> : <IndentIcon />}
    </ToolbarButton>
  );
}
