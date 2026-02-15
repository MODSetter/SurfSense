'use client';

import type { AutoformatBlockRule, AutoformatRule } from '@platejs/autoformat';
import type { SlateEditor } from 'platejs';

import {
  autoformatArrow,
  autoformatLegal,
  autoformatLegalHtml,
  autoformatMath,
  AutoformatPlugin,
  autoformatPunctuation,
  autoformatSmartQuotes,
} from '@platejs/autoformat';
import { insertEmptyCodeBlock } from '@platejs/code-block';
import { toggleList, toggleTaskList, unwrapList } from '@platejs/list-classic';
import { openNextToggles } from '@platejs/toggle/react';
import { ElementApi, isType, KEYS } from 'platejs';

const preFormat: AutoformatBlockRule['preFormat'] = (editor) =>
  unwrapList(editor);

const format = (editor: SlateEditor, customFormatting: any) => {
  if (editor.selection) {
    const parentEntry = editor.api.parent(editor.selection);

    if (!parentEntry) return;

    const [node] = parentEntry;

    if (ElementApi.isElement(node) && !isType(editor, node, KEYS.codeBlock)) {
      customFormatting();
    }
  }
};

const formatTaskList = (editor: SlateEditor, defaultChecked = false) => {
  format(editor, () => toggleTaskList(editor, defaultChecked));
};

const formatList = (editor: SlateEditor, elementType: string) => {
  format(editor, () =>
    toggleList(editor, {
      type: elementType,
    })
  );
};

const autoformatMarks: AutoformatRule[] = [
  {
    match: '***',
    mode: 'mark',
    type: [KEYS.bold, KEYS.italic],
  },
  {
    match: '__*',
    mode: 'mark',
    type: [KEYS.underline, KEYS.italic],
  },
  {
    match: '__**',
    mode: 'mark',
    type: [KEYS.underline, KEYS.bold],
  },
  {
    match: '___***',
    mode: 'mark',
    type: [KEYS.underline, KEYS.bold, KEYS.italic],
  },
  {
    match: '**',
    mode: 'mark',
    type: KEYS.bold,
  },
  {
    match: '__',
    mode: 'mark',
    type: KEYS.underline,
  },
  {
    match: '*',
    mode: 'mark',
    type: KEYS.italic,
  },
  {
    match: '_',
    mode: 'mark',
    type: KEYS.italic,
  },
  {
    match: '~~',
    mode: 'mark',
    type: KEYS.strikethrough,
  },
  {
    match: '^',
    mode: 'mark',
    type: KEYS.sup,
  },
  {
    match: '~',
    mode: 'mark',
    type: KEYS.sub,
  },
  {
    match: '==',
    mode: 'mark',
    type: KEYS.highlight,
  },
  {
    match: '≡',
    mode: 'mark',
    type: KEYS.highlight,
  },
  {
    match: '`',
    mode: 'mark',
    type: KEYS.code,
  },
];

const autoformatBlocks: AutoformatRule[] = [
  {
    match: '# ',
    mode: 'block',
    preFormat,
    type: KEYS.h1,
  },
  {
    match: '## ',
    mode: 'block',
    preFormat,
    type: KEYS.h2,
  },
  {
    match: '### ',
    mode: 'block',
    preFormat,
    type: KEYS.h3,
  },
  {
    match: '#### ',
    mode: 'block',
    preFormat,
    type: KEYS.h4,
  },
  {
    match: '##### ',
    mode: 'block',
    preFormat,
    type: KEYS.h5,
  },
  {
    match: '###### ',
    mode: 'block',
    preFormat,
    type: KEYS.h6,
  },
  {
    match: '> ',
    mode: 'block',
    preFormat,
    type: KEYS.blockquote,
  },
  {
    match: '```',
    mode: 'block',
    preFormat,
    type: KEYS.codeBlock,
    format: (editor) => {
      insertEmptyCodeBlock(editor, {
        defaultType: KEYS.p,
        insertNodesOptions: { select: true },
      });
    },
  },
  {
    match: '+ ',
    mode: 'block',
    preFormat: openNextToggles,
    type: KEYS.toggle,
  },
  {
    match: ['---', '—-', '___ '],
    mode: 'block',
    type: KEYS.hr,
    format: (editor) => {
      editor.tf.setNodes({ type: KEYS.hr });
      editor.tf.insertNodes({
        children: [{ text: '' }],
        type: KEYS.p,
      });
    },
  },
];

const autoformatLists: AutoformatRule[] = [
  {
    match: ['* ', '- '],
    mode: 'block',
    preFormat,
    type: KEYS.li,
    format: (editor) => formatList(editor, KEYS.ulClassic),
  },
  {
    match: [String.raw`^\d+\.$ `, String.raw`^\d+\)$ `],
    matchByRegex: true,
    mode: 'block',
    preFormat,
    type: KEYS.li,
    format: (editor) => formatList(editor, KEYS.olClassic),
  },
  {
    match: '[] ',
    mode: 'block',
    type: KEYS.taskList,
    format: (editor) => formatTaskList(editor, false),
  },
  {
    match: '[x] ',
    mode: 'block',
    type: KEYS.taskList,
    format: (editor) => formatTaskList(editor, true),
  },
];

export const AutoformatKit = [
  AutoformatPlugin.configure({
    options: {
      enableUndoOnDelete: true,
      rules: [
        ...autoformatBlocks,
        ...autoformatMarks,
        ...autoformatSmartQuotes,
        ...autoformatPunctuation,
        ...autoformatLegal,
        ...autoformatLegalHtml,
        ...autoformatArrow,
        ...autoformatMath,
        ...autoformatLists,
      ].map((rule) => ({
        ...rule,
        query: (editor) =>
          !editor.api.some({
            match: { type: editor.getType(KEYS.codeBlock) },
          }),
      })),
    },
  }),
];
