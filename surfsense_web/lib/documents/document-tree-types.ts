export interface DocumentNodeDoc {
	id: number;
	title: string;
	document_type: string;
	folderId: number | null;
	createdAt: number;
	status?: { state: string; reason?: string | null };
	/** Present for ARTIFACT documents after REST sidecar reconciliation. */
	artifactFormat?: string;
}

export interface FolderDisplay {
	id: number;
	name: string;
	position: string;
	parentId: number | null;
	workspaceId: number;
	metadata?: Record<string, unknown> | null;
}

export type FolderSelectionState = "all" | "some" | "none";
