'use client';

import { createPlatePlugin } from 'platejs/react';

import { FloatingToolbar } from '@/components/ui/floating-toolbar';
import { FloatingToolbarButtons } from '@/components/ui/floating-toolbar-buttons';

export const FloatingToolbarKit = [
  createPlatePlugin({
    key: 'floating-toolbar',
    render: {
      afterEditable: () => (
        <FloatingToolbar>
          <FloatingToolbarButtons />
        </FloatingToolbar>
      ),
    },
  }),
];
