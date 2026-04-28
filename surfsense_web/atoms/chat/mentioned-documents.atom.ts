"use client";

import { atom } from "jotai";
import type { Document } from "@/contracts/types/document.types";

/**
 * Atom to store the full document objects mentioned via @-mention chips
 * in the current chat composer. This persists across component remounts.
 */
export const mentionedDocumentsAtom = atom<Pick<Document, "id" | "title" | "document_type">[]>([]);

/**
 * Atom to store documents selected via the sidebar checkboxes / row clicks.
 * These power the selected-sources badge and backend doc filters.
 */
export const sidebarSelectedDocumentsAtom = atom<
	Pick<Document, "id" | "title" | "document_type">[]
>([]);

export interface SidebarMentionEvent {
	kind: "add" | "remove";
	docs: Pick<Document, "id" | "title" | "document_type">[];
	nonce: number;
}

/**
 * Event atom used to tell the composer that documents were selected/unselected
 * from sidebar checkboxes, so chips can be inserted/removed in-editor.
 */
export const sidebarMentionEventAtom = atom<SidebarMentionEvent | null>(null);

/**
 * Derived read-only atom that merges @-mention chips and sidebar selections
 * into a single deduplicated set of document IDs for the backend.
 */
export const mentionedDocumentIdsAtom = atom((get) => {
	const chipDocs = get(mentionedDocumentsAtom);
	const sidebarDocs = get(sidebarSelectedDocumentsAtom);
	const allDocs = [...chipDocs, ...sidebarDocs];
	const seen = new Set<string>();
	const deduped = allDocs.filter((d) => {
		const key = `${d.document_type}:${d.id}`;
		if (seen.has(key)) return false;
		seen.add(key);
		return true;
	});
	return {
		surfsense_doc_ids: deduped
			.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
			.map((doc) => doc.id),
		document_ids: deduped
			.filter((doc) => doc.document_type !== "SURFSENSE_DOCS")
			.map((doc) => doc.id),
	};
});

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
