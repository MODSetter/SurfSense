'use client';

import * as React from 'react';

import type { DropdownMenuProps } from '@radix-ui/react-dropdown-menu';

import { insertInlineEquation } from '@platejs/math';
import {
  InfoIcon,
  KeyboardIcon,
  MoreHorizontalIcon,
  RadicalIcon,
  SubscriptIcon,
  SuperscriptIcon,
} from 'lucide-react';
import { KEYS } from 'platejs';
import { useEditorRef } from 'platejs/react';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

import { ToolbarButton } from './toolbar';

export function MoreToolbarButton(props: DropdownMenuProps) {
  const editor = useEditorRef();
  const [open, setOpen] = React.useState(false);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen} modal={false} {...props}>
      <DropdownMenuTrigger asChild>
        <ToolbarButton pressed={open} tooltip="Insert">
          <MoreHorizontalIcon />
        </ToolbarButton>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        className="ignore-click-outside/toolbar flex max-h-[500px] min-w-[180px] flex-col overflow-y-auto"
        align="start"
      >
        <DropdownMenuGroup>
          <DropdownMenuItem
            onSelect={() => {
              editor.tf.toggleMark(KEYS.kbd);
              editor.tf.collapse({ edge: 'end' });
              editor.tf.focus();
            }}
          >
            <KeyboardIcon />
            Keyboard input
          </DropdownMenuItem>

          <DropdownMenuItem
            onSelect={() => {
              editor.tf.toggleMark(KEYS.sup, {
                remove: KEYS.sub,
              });
              editor.tf.focus();
            }}
          >
            <SuperscriptIcon />
            Superscript
            {/* (⌘+,) */}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              editor.tf.toggleMark(KEYS.sub, {
                remove: KEYS.sup,
              });
              editor.tf.focus();
            }}
          >
            <SubscriptIcon />
            Subscript
            {/* (⌘+.) */}
          </DropdownMenuItem>

          <DropdownMenuItem
            onSelect={() => {
              insertInlineEquation(editor);
              editor.tf.focus();
            }}
          >
            <RadicalIcon />
            Equation
          </DropdownMenuItem>

          <DropdownMenuItem
            onSelect={() => {
              editor.tf.insertNodes(
                editor.api.create.block({ type: KEYS.callout }),
                { select: true }
              );
              editor.tf.focus();
            }}
          >
            <InfoIcon />
            Callout
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
