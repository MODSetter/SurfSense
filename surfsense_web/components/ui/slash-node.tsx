'use client';

import * as React from 'react';

import type { PlateElementProps } from 'platejs/react';

import { SlashInputPlugin } from '@platejs/slash-command/react';
import {
  ChevronRightIcon,
  Code2Icon,
  Columns2Icon,
  FileCodeIcon,
  Heading1Icon,
  Heading2Icon,
  Heading3Icon,
  InfoIcon,
  ListIcon,
  ListOrderedIcon,
  MinusIcon,
  PilcrowIcon,
  QuoteIcon,
  RadicalIcon,
  SquareIcon,
  TableIcon,
} from 'lucide-react';
import { KEYS } from 'platejs';
import { PlateElement, useEditorPlugin, useEditorRef } from 'platejs/react';

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { insertBlock, insertInlineElement } from '@/components/editor/transforms';

interface SlashCommandItem {
  icon: React.ReactNode;
  keywords: string[];
  label: string;
  onSelect: (editor: any) => void;
}

const slashCommandGroups: { heading: string; items: SlashCommandItem[] }[] = [
  {
    heading: 'Basic Blocks',
    items: [
      {
        icon: <PilcrowIcon />,
        keywords: ['paragraph', 'text', 'plain'],
        label: 'Text',
        onSelect: (editor) => insertBlock(editor, KEYS.p),
      },
      {
        icon: <Heading1Icon />,
        keywords: ['title', 'h1', 'heading'],
        label: 'Heading 1',
        onSelect: (editor) => insertBlock(editor, 'h1'),
      },
      {
        icon: <Heading2Icon />,
        keywords: ['subtitle', 'h2', 'heading'],
        label: 'Heading 2',
        onSelect: (editor) => insertBlock(editor, 'h2'),
      },
      {
        icon: <Heading3Icon />,
        keywords: ['subtitle', 'h3', 'heading'],
        label: 'Heading 3',
        onSelect: (editor) => insertBlock(editor, 'h3'),
      },
      {
        icon: <QuoteIcon />,
        keywords: ['citation', 'blockquote'],
        label: 'Quote',
        onSelect: (editor) => insertBlock(editor, KEYS.blockquote),
      },
      {
        icon: <MinusIcon />,
        keywords: ['divider', 'separator', 'line'],
        label: 'Divider',
        onSelect: (editor) => insertBlock(editor, KEYS.hr),
      },
    ],
  },
  {
    heading: 'Lists',
    items: [
      {
        icon: <ListIcon />,
        keywords: ['unordered', 'ul', 'bullet'],
        label: 'Bulleted list',
        onSelect: (editor) => insertBlock(editor, KEYS.ul),
      },
      {
        icon: <ListOrderedIcon />,
        keywords: ['ordered', 'ol', 'numbered'],
        label: 'Numbered list',
        onSelect: (editor) => insertBlock(editor, KEYS.ol),
      },
      {
        icon: <SquareIcon />,
        keywords: ['checklist', 'task', 'checkbox', 'todo'],
        label: 'To-do list',
        onSelect: (editor) => insertBlock(editor, KEYS.listTodo),
      },
    ],
  },
  {
    heading: 'Advanced',
    items: [
      {
        icon: <TableIcon />,
        keywords: ['table', 'grid'],
        label: 'Table',
        onSelect: (editor) => insertBlock(editor, KEYS.table),
      },
      {
        icon: <FileCodeIcon />,
        keywords: ['code', 'codeblock', 'snippet'],
        label: 'Code block',
        onSelect: (editor) => insertBlock(editor, KEYS.codeBlock),
      },
      {
        icon: <InfoIcon />,
        keywords: ['callout', 'note', 'info', 'warning', 'tip'],
        label: 'Callout',
        onSelect: (editor) => insertBlock(editor, KEYS.callout),
      },
      {
        icon: <ChevronRightIcon />,
        keywords: ['toggle', 'collapsible', 'expand'],
        label: 'Toggle',
        onSelect: (editor) => insertBlock(editor, KEYS.toggle),
      },
      {
        icon: <RadicalIcon />,
        keywords: ['equation', 'math', 'formula', 'latex'],
        label: 'Equation',
        onSelect: (editor) => insertInlineElement(editor, KEYS.equation),
      },
    ],
  },
  {
    heading: 'Inline',
    items: [
      {
        icon: <Code2Icon />,
        keywords: ['link', 'url', 'href'],
        label: 'Link',
        onSelect: (editor) => insertInlineElement(editor, KEYS.link),
      },
    ],
  },
];

export function SlashInputElement({
  children,
  ...props
}: PlateElementProps) {
  const { editor, setOption } = useEditorPlugin(SlashInputPlugin);

  return (
    <PlateElement {...props} as="span">
      <Command
        className="relative z-50 min-w-[280px] overflow-hidden rounded-lg border bg-popover shadow-md"
        shouldFilter={true}
      >
        <CommandInput
          className="hidden"
          value={props.element.value as string}
          onValueChange={(value) => {
            // The value is managed by the slash input plugin
          }}
          autoFocus
        />
        <CommandList className="max-h-[300px] overflow-y-auto p-1">
          <CommandEmpty>No results found.</CommandEmpty>
          {slashCommandGroups.map(({ heading, items }) => (
            <CommandGroup key={heading} heading={heading}>
              {items.map(({ icon, keywords, label, onSelect }) => (
                <CommandItem
                  key={label}
                  className="flex items-center gap-2 px-2"
                  keywords={keywords}
                  value={label}
                  onSelect={() => {
                    editor.tf.removeNodes({
                      match: (n) => (n as any).type === SlashInputPlugin.key,
                    });
                    onSelect(editor);
                    editor.tf.focus();
                  }}
                >
                  <span className="flex size-5 items-center justify-center text-muted-foreground">
                    {icon}
                  </span>
                  {label}
                </CommandItem>
              ))}
            </CommandGroup>
          ))}
        </CommandList>
      </Command>
      {children}
    </PlateElement>
  );
}

