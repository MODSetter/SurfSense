"use client";

import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

/**
 * Set of folder IDs that are currently expanded in the tree, keyed by search space ID.
 * Persisted to localStorage so expand/collapse state survives page refreshes.
 */
export const expandedFolderIdsAtom = atomWithStorage<Record<number, number[]>>(
	"surfsense:expandedFolderIds",
	{},
);

/**
 * Folder currently being renamed (inline edit mode).
 * null means no folder is being renamed.
 */
export const renamingFolderIdAtom = atom<number | null>(null);
