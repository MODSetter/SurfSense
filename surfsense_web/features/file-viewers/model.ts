export interface ViewableFile {
	filename: string;
	mime_type: string;
	size_bytes: number;
	content_url: string;
	role?: string;
}

export interface FileViewerProps {
	primary: ViewableFile;
	files: readonly ViewableFile[];
	zoomControlsContainer?: HTMLElement | null;
}
