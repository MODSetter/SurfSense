import { BaseLinkPlugin } from '@platejs/link';

import { LinkElementStatic } from '@/components/ui/link-node-static';

export const BaseLinkKit = [BaseLinkPlugin.withComponent(LinkElementStatic)];
