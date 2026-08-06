export interface ArtifactFile {
	file_id: number;
	role: "primary" | "preview";
	filename: string;
	mime_type: string;
	size_bytes: number;
	content_url: string;
}

export interface TextArtifactContent {
	kind: "text";
	document_id: number;
	title: string;
	source_markdown: string;
	generated: boolean;
	updated_at: string | null;
}

export interface FileArtifactContent {
	kind: "file";
	document_id: number;
	title: string;
	generated: boolean;
	files: ArtifactFile[];
	updated_at: string | null;
}

export type ArtifactContent = TextArtifactContent | FileArtifactContent;
