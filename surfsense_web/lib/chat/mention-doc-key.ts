type MentionKeyInput = {
	id: number;
	document_type?: string | null;
	kind?: "doc" | "folder";
};

/**
 * Build a stable dedup key for a mention chip.
 *
 * The ``kind:document_type:id`` shape prevents a document and a folder
 * with the same integer id from colliding in the chip array (folders
 * use the ``FOLDER`` sentinel ``document_type``; the ``kind`` prefix
 * is the belt-and-braces guard).
 */
export function getMentionDocKey(doc: MentionKeyInput): string {
	const kind = doc.kind ?? "doc";
	return `${kind}:${doc.document_type ?? "UNKNOWN"}:${doc.id}`;
}
