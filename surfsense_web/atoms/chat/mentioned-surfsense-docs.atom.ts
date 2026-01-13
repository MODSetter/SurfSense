"use client";

import { atom } from "jotai";
import type { SurfsenseDocsDocument } from "@/contracts/types/document.types";

/**
 * Atom to store the IDs of SurfSense docs mentioned in the current chat composer.
 * This is used to pass documentation context to the backend when sending a message.
 */
export const mentionedSurfsenseDocIdsAtom = atom<number[]>([]);

/**
 * Atom to store the full SurfSense doc objects mentioned in the current chat composer.
 * This persists across component remounts.
 */
export const mentionedSurfsenseDocsAtom = atom<SurfsenseDocsDocument[]>([]);

/**
 * Simplified SurfSense doc info for display purposes
 */
export interface MentionedSurfsenseDocInfo {
	id: number;
	title: string;
	source: string;
}

/**
 * Atom to store mentioned SurfSense docs per message ID.
 * This allows displaying which docs were mentioned with each user message.
 */
export const messageSurfsenseDocsMapAtom = atom<Record<string, MentionedSurfsenseDocInfo[]>>({});

