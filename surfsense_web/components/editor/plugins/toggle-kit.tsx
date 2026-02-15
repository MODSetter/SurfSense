'use client';

import { TogglePlugin } from '@platejs/toggle/react';

import { ToggleElement } from '@/components/ui/toggle-node';

export const ToggleKit = [
  TogglePlugin.configure({
    node: { component: ToggleElement },
    shortcuts: { toggle: { keys: 'mod+alt+9' } },
  }),
];

