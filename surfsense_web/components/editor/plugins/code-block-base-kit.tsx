import {
  BaseCodeBlockPlugin,
  BaseCodeLinePlugin,
  BaseCodeSyntaxPlugin,
} from '@platejs/code-block';
import { all, createLowlight } from 'lowlight';

import {
  CodeBlockElementStatic,
  CodeLineElementStatic,
  CodeSyntaxLeafStatic,
} from '@/components/ui/code-block-node-static';

const lowlight = createLowlight(all);

export const BaseCodeBlockKit = [
  BaseCodeBlockPlugin.configure({
    node: { component: CodeBlockElementStatic },
    options: { lowlight },
  }),
  BaseCodeLinePlugin.withComponent(CodeLineElementStatic),
  BaseCodeSyntaxPlugin.withComponent(CodeSyntaxLeafStatic),
];
