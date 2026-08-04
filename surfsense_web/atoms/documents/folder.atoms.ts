"use client";

import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

/**
 * Set of folder IDs that are currently expanded in the tree, keyed by workspace ID.
 * Persisted to localStorage so expand/collapse state survives page refreshes.
 */
export const expandedFolderIdsAtom = atomWithStorage<Record<number, number[]>>(
	"surfsense:expandedFolderIds",
	{}
);

/**
 * Expanded folder keys for Local filesystem tree, keyed by workspace ID.
 * Persisted so local tree expansion survives remounts/reloads.
 */
export const localExpandedFolderKeysAtom = atomWithStorage<Record<number, string[]>>(
	"surfsense:localExpandedFolderKeys",
	{}
);

/**
 * Folder currently being renamed (inline edit mode).
 * null means no folder is being renamed.
 */
export const renamingFolderIdAtom = atom<number | null>(null);

/**
 * Bumped whenever a folder is (un)watched outside DocumentRightPanel (e.g. the
 * sidebar-footer "Watch Local Folder" button) so the tree re-reads Electron's
 * watched-folder list and shows the sync badge without a reload.
 */
export const watchedFoldersRefreshAtom = atom(0);
