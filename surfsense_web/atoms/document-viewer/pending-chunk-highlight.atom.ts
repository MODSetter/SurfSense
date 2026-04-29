import { atom } from "jotai";

/**
 * Cross-component handoff for citation jumps. Set by `InlineCitation` when a
 * numeric chunk badge is clicked (after the document has been resolved); read
 * by `DocumentTabContent` once the matching document tab mounts so it can
 * scroll to and softly highlight the cited chunk inside the rendered markdown.
 *
 * Cleared by `DocumentTabContent` only after a terminal state — exact /
 * approximate / miss — has been reached, so that an escalation refetch (2MB
 * preview → 16MB) keeps the pending intent alive across the re-render.
 */
export interface PendingChunkHighlight {
	documentId: number;
	chunkId: number;
	chunkText: string;
}

export const pendingChunkHighlightAtom = atom<PendingChunkHighlight | null>(null);
