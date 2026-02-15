import * as React from 'react';

import type { SlateLeafProps } from 'platejs/static';

import { SlateLeaf } from 'platejs/static';

export function HighlightLeafStatic(props: SlateLeafProps) {
  return (
    <SlateLeaf {...props} as="mark" className="bg-highlight/30 text-inherit">
      {props.children}
    </SlateLeaf>
  );
}
