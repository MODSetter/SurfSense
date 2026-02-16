'use client';

import * as React from 'react';
import { createPortal } from 'react-dom';

import type { PlateElementProps } from 'platejs/react';

import { SlashInputPlugin } from '@platejs/slash-command/react';
import {
  ChevronRightIcon,
  Code2Icon,
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
  const anchorRef = React.useRef<HTMLSpanElement>(null);
  const [menuPosition, setMenuPosition] = React.useState<{ top: number; left: number } | null>(null);

  React.useEffect(() => {
    const updatePosition = () => {
      if (anchorRef.current) {
        const rect = anchorRef.current.getBoundingClientRect();
        setMenuPosition({
          top: rect.bottom + window.scrollY,
          left: rect.left + window.scrollX,
        });
      }
    };

    updatePosition();

    // Re-position on scroll/resize since the editor may scroll
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, []);

  return (
    <PlateElement {...props} as="span">
      <span ref={anchorRef} />
      {menuPosition &&
        createPortal(
          <Command
            className="fixed z-50 w-[330px] overflow-hidden rounded-lg border bg-popover shadow-lg"
            style={{ top: menuPosition.top, left: menuPosition.left }}
            shouldFilter={false}
          >
            <CommandList className="max-h-[min(400px,40vh)] overflow-y-auto p-1">
              <CommandEmpty>No results found.</CommandEmpty>
              {slashCommandGroups.map(({ heading, items }) => (
                <CommandGroup key={heading} heading={heading}>
                  {items.map(({ icon, keywords, label, onSelect }) => (
                    <CommandItem
                      key={label}
                      className="flex items-center gap-3 px-2 py-2"
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
          </Command>,
          document.body
        )}
      {children}
    </PlateElement>
  );
}

