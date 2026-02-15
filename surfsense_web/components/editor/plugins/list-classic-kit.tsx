'use client';

import {
  BulletedListPlugin,
  ListItemContentPlugin,
  ListItemPlugin,
  ListPlugin,
  NumberedListPlugin,
  TaskListPlugin,
} from '@platejs/list-classic/react';

import {
  BulletedListElement,
  ListItemElement,
  NumberedListElement,
  TaskListElement,
} from '@/components/ui/list-classic-node';

export const ListKit = [
  ListPlugin,
  ListItemPlugin,
  ListItemContentPlugin,
  BulletedListPlugin.configure({
    node: { component: BulletedListElement },
    shortcuts: { toggle: { keys: 'mod+alt+5' } },
  }),
  NumberedListPlugin.configure({
    node: { component: NumberedListElement },
    shortcuts: { toggle: { keys: 'mod+alt+6' } },
  }),
  TaskListPlugin.configure({
    node: { component: TaskListElement },
    shortcuts: { toggle: { keys: 'mod+alt+7' } },
  }),
  ListItemPlugin.withComponent(ListItemElement),
];
