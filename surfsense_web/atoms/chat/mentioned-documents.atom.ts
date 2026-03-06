"use client";

import { atom } from "jotai";
import type { Document } from "@/contracts/types/document.types";

/**
 * Atom to store the IDs of documents mentioned in the current chat composer.
 * This is used to pass document context to the backend when sending a message.
 */
export const mentionedDocumentIdsAtom = atom<{
	surfsense_doc_ids: number[];
	document_ids: number[];
}>({
	surfsense_doc_ids: [],
	document_ids: [],
});

/**
 * Atom to store the full document objects mentioned via @-mention chips
 * in the current chat composer. This persists across component remounts.
 */
export const mentionedDocumentsAtom = atom<Pick<Document, "id" | "title" | "document_type">[]>([]);

/**
 * Atom to store documents selected via the sidebar checkboxes / row clicks.
 * These are NOT inserted as chips – the composer shows a count badge instead.
 */
export const sidebarSelectedDocumentsAtom = atom<Pick<Document, "id" | "title" | "document_type">[]>([]);

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
