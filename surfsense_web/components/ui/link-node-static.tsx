import * as React from 'react';

import type { TLinkElement } from 'platejs';
import type { SlateElementProps } from 'platejs/static';

import { getLinkAttributes } from '@platejs/link';
import { SlateElement } from 'platejs/static';

export function LinkElementStatic(props: SlateElementProps<TLinkElement>) {
  return (
    <SlateElement
      {...props}
      as="a"
      className="font-medium text-primary underline decoration-primary underline-offset-4"
      attributes={{
        ...props.attributes,
        ...getLinkAttributes(props.editor, props.element),
      }}
    >
      {props.children}
    </SlateElement>
  );
}
