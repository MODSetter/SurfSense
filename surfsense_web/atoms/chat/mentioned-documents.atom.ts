"use client";

import { atom } from "jotai";
import type { Document } from "@/contracts/types/document.types";

/**
 * Atom to store the full document objects mentioned via @-mention chips
 * in the current chat composer. This persists across component remounts.
 */
export const mentionedDocumentsAtom = atom<Pick<Document, "id" | "title" | "document_type">[]>([]);

/**
 * Back-compat alias for sidebar checkbox selection.
 * This now points to mentionedDocumentsAtom so the app has a single source
 * of truth for mentioned/selected documents.
 */
export const sidebarSelectedDocumentsAtom = atom<
	Pick<Document, "id" | "title" | "document_type">[],
	[
		| Pick<Document, "id" | "title" | "document_type">[]
		| ((
				prev: Pick<Document, "id" | "title" | "document_type">[]
		  ) => Pick<Document, "id" | "title" | "document_type">[]),
	],
	void
>(
	(get) => get(mentionedDocumentsAtom),
	(get, set, update) => {
		const prev = get(mentionedDocumentsAtom);
		const next = typeof update === "function" ? update(prev) : update;
		set(mentionedDocumentsAtom, next);
	}
);

/**
 * Derived read-only atom that maps deduplicated mentioned docs
 * into backend payload fields.
 */
export const mentionedDocumentIdsAtom = atom((get) => {
	const allDocs = get(mentionedDocumentsAtom);
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
