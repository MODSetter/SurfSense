"use client";

import { atom } from "jotai";
import type { Document } from "@/contracts/types/document.types";

/**
 * Sentinel ``document_type`` used for folder mention chips so the
 * dedup key (`kind:document_type:id`) never collides a document with a
 * folder that happens to share an integer id.
 */
export const FOLDER_MENTION_DOCUMENT_TYPE = "FOLDER";

/**
 * Display metadata for a single ``@``-mention chip.
 *
 * The ``kind`` discriminator identifies whether the chip is a
 * knowledge-base document or a knowledge-base folder. Folders carry
 * the sentinel ``document_type === FOLDER_MENTION_DOCUMENT_TYPE`` so
 * the editor, picker, and persisted ``mentioned-documents`` content
 * part all stay aligned with the backend Pydantic schema.
 */
export interface MentionedDocumentInfo {
	id: number;
	title: string;
	document_type: string;
	kind: "doc" | "folder";
}

/**
 * Backwards-compatible doc-only chip shape for legacy callers that
 * haven't migrated to the discriminated union yet. Keep narrow so
 * accidental new callers fail typecheck and route through the
 * discriminated type instead.
 */
type LegacyDocMention = Pick<Document, "id" | "title" | "document_type">;

/**
 * Normalize an arbitrary chip-like input into the discriminated
 * ``MentionedDocumentInfo`` shape. Existing call sites that only have
 * ``{id, title, document_type}`` flow through here so they don't have
 * to thread ``kind`` everywhere — the helper defaults to ``"doc"`` and
 * rewrites the document type for folders.
 */
export function toMentionedDocumentInfo(
	input: LegacyDocMention | MentionedDocumentInfo
): MentionedDocumentInfo {
	if ("kind" in input && (input.kind === "doc" || input.kind === "folder")) {
		return input;
	}
	return {
		id: input.id,
		title: input.title,
		document_type: input.document_type,
		kind: "doc",
	};
}

/**
 * Build a folder-mention chip from a folder row (id + name).
 */
export function makeFolderMention(input: { id: number; name: string }): MentionedDocumentInfo {
	return {
		id: input.id,
		title: input.name,
		document_type: FOLDER_MENTION_DOCUMENT_TYPE,
		kind: "folder",
	};
}

/**
 * Atom to store the full mention objects (documents + folders) attached
 * via @-mention chips in the current chat composer. Persists across
 * component remounts.
 */
export const mentionedDocumentsAtom = atom<MentionedDocumentInfo[]>([]);

/**
 * Derived read-only atom that maps deduplicated mention chips into
 * backend payload fields. Doc chips split by ``document_type`` exactly
 * like before; folder chips are projected into a separate
 * ``folder_ids`` bucket so the route can forward
 * ``mentioned_folder_ids`` to the agent without the priority middleware
 * conflating them with hybrid-search ids.
 */
export const mentionedDocumentIdsAtom = atom((get) => {
	const allMentions = get(mentionedDocumentsAtom);
	const seen = new Set<string>();
	const deduped = allMentions.filter((m) => {
		const key = `${m.kind}:${m.document_type}:${m.id}`;
		if (seen.has(key)) return false;
		seen.add(key);
		return true;
	});
	const docs = deduped.filter((m) => m.kind === "doc");
	const folders = deduped.filter((m) => m.kind === "folder");
	return {
		surfsense_doc_ids: docs
			.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
			.map((doc) => doc.id),
		document_ids: docs.filter((doc) => doc.document_type !== "SURFSENSE_DOCS").map((doc) => doc.id),
		folder_ids: folders.map((f) => f.id),
	};
});

/**
 * Atom to store mentioned chips per message ID.
 * This allows displaying which documents were mentioned with each user message.
 */
export const messageDocumentsMapAtom = atom<Record<string, MentionedDocumentInfo[]>>({});
