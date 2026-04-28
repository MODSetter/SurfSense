type MentionKeyInput = {
	id: number;
	document_type?: string | null;
};

export function getMentionDocKey(doc: MentionKeyInput): string {
	return `${doc.document_type ?? "UNKNOWN"}:${doc.id}`;
}
