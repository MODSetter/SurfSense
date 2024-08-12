import React from 'react';
import MarkdownPreview from '@uiw/react-markdown-preview';

export default function MarkDownTest({source} : {source: string}) {
  return (
    <MarkdownPreview source={source} style={{ padding: 16 }} />
  )
}