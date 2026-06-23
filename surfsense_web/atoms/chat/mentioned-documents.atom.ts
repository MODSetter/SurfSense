"use client";

import { atom } from "jotai";
import type { Document } from "@/contracts/types/document.types";

/**
 * Display metadata for a single ``@``-mention chip.
 *
 * Historical name is retained because this atom is already wired into
 * chat persistence and sidebar selection. The shape is now the selected
 * composer context, not only documents.
 */
export type MentionedDocumentInfo =
	| {
			id: number;
			title: string;
			document_type: string;
			kind: "doc";
	  }
	| {
			id: number;
			title: string;
			kind: "folder";
	  }
	| {
			id: number;
			title: string;
			kind: "connector";
			connector_type: string;
			account_name: string;
	  }
	| {
			id: number;
			title: string;
			kind: "thread";
	  };

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
 * to thread ``kind`` everywhere — the helper defaults to ``"doc"``.
 */
export function toMentionedDocumentInfo(
	input: LegacyDocMention | MentionedDocumentInfo
): MentionedDocumentInfo {
	if (
		"kind" in input &&
		(input.kind === "doc" ||
			input.kind === "folder" ||
			input.kind === "connector" ||
			input.kind === "thread")
	) {
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
		kind: "folder",
	};
}

/**
 * Build a thread-mention chip from a thread row (id + title). Used to
 * reference another conversation as read-only context.
 */
export function makeThreadMention(input: { id: number; title: string }): MentionedDocumentInfo {
	return {
		id: input.id,
		title: input.title,
		kind: "thread",
	};
}

/**
 * Atom to store the full context objects attached via @-mention chips in
 * the current chat composer. Persists across component remounts.
 */
export const mentionedDocumentsAtom = atom<MentionedDocumentInfo[]>([]);

/**
 * Chips captured at submit time, so they survive the composer resetting
 * the live atom on send. Consumed (and reset) by the send handler.
 */
export const submittedMentionsAtom = atom<MentionedDocumentInfo[] | null>(null);

/**
 * Map mention chips to their backend payload buckets. Each kind gets its
 * own bucket so non-document context never masquerades as a document.
 */
export function deriveMentionedPayload(mentions: ReadonlyArray<MentionedDocumentInfo>) {
	const seen = new Set<string>();
	const deduped = mentions.filter((m) => {
		const key =
			m.kind === "doc"
				? `doc:${m.document_type}:${m.id}`
				: m.kind === "connector"
					? `connector:${m.connector_type}:${m.id}`
					: m.kind === "thread"
						? `thread:${m.id}`
						: `folder:${m.id}`;
		if (seen.has(key)) return false;
		seen.add(key);
		return true;
	});
	const docs = deduped.filter((m) => m.kind === "doc");
	const folders = deduped.filter((m) => m.kind === "folder");
	const connectors = deduped.filter((m) => m.kind === "connector");
	const threads = deduped.filter((m) => m.kind === "thread");
	return {
		document_ids: docs.map((doc) => doc.id),
		folder_ids: folders.map((f) => f.id),
		connector_ids: connectors.map((c) => c.id),
		thread_ids: threads.map((t) => t.id),
		connectors: connectors.map((c) => ({
			id: c.id,
			title: c.title,
			kind: c.kind,
			connector_type: c.connector_type,
			account_name: c.account_name,
		})),
	};
}

/**
 * Atom to store mentioned chips per message ID.
 * This allows displaying which documents were mentioned with each user message.
 */
export const messageDocumentsMapAtom = atom<Record<string, MentionedDocumentInfo[]>>({});
