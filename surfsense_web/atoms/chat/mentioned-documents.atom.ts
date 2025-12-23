"use client";

import { atom } from "jotai";
import type { Document } from "@/contracts/types/document.types";

/**
 * Atom to store the IDs of documents mentioned in the current chat composer.
 * This is used to pass document context to the backend when sending a message.
 */
export const mentionedDocumentIdsAtom = atom<number[]>([]);

/**
 * Atom to store the full document objects mentioned in the current chat composer.
 * This persists across component remounts.
 */
export const mentionedDocumentsAtom = atom<Document[]>([]);

/**
 * Simplified document info for display purposes
 */
export interface MentionedDocumentInfo {
	id: number;
	title: string;
	document_type: string;
}

/**
 * Atom to store mentioned documents per message ID.
 * This allows displaying which documents were mentioned with each user message.
 */
export const messageDocumentsMapAtom = atom<Record<string, MentionedDocumentInfo[]>>({});

