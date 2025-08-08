export type DocumentType = string;

export type Document = {
	id: number;
	title: string;
	document_type: DocumentType;
	document_metadata: any;
	content: string;
	created_at: string;
	search_space_id: number;
};

export type ColumnVisibility = {
	title: boolean;
	document_type: boolean;
	content: boolean;
	created_at: boolean;
};
