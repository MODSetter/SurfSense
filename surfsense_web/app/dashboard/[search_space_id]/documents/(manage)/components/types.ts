export type DocumentType = string;

export type Document = {
	id: number;
	title: string;
	document_type: DocumentType;
	document_metadata: any;
	content: string;
	created_at: string;
	search_space_id: number;
	created_by_id?: string | null;
	created_by_name?: string | null;
};

export type ColumnVisibility = {
	document_type: boolean;
	created_by: boolean;
	created_at: boolean;
};
