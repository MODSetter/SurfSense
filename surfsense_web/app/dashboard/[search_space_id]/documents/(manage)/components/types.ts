export type DocumentType = string;

export type DocumentStatus = {
	state: "ready" | "pending" | "processing" | "failed";
	reason?: string;
};

export type Document = {
	id: number;
	title: string;
	document_type: DocumentType;
	// Optional: Only needed when viewing document details (lazy loaded)
	document_metadata?: any;
	content?: string;
	created_at: string;
	search_space_id: number;
	created_by_id?: string | null;
	created_by_name?: string | null;
	created_by_email?: string | null;
	status?: DocumentStatus;
};

export type ColumnVisibility = {
	document_type: boolean;
	created_by: boolean;
	created_at: boolean;
	status: boolean;
};
