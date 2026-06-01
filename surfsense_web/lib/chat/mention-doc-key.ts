type MentionKeyInput = {
	id: number;
	document_type?: string | null;
	connector_type?: string | null;
	kind?: "doc" | "folder" | "connector";
};

/**
 * Build a stable dedup key for a mention chip.
 *
 * Each mention kind keys off its real identity fields:
 * docs by document type, folders by folder id, and connectors by
 * connector type + account id.
 */
export function getMentionDocKey(doc: MentionKeyInput): string {
	const kind = doc.kind ?? "doc";
	if (kind === "folder") return `folder:${doc.id}`;
	if (kind === "connector") return `connector:${doc.connector_type ?? "UNKNOWN"}:${doc.id}`;
	return `doc:${doc.document_type ?? "UNKNOWN"}:${doc.id}`;
}
