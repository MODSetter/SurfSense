declare module "dom-to-pptx" {
	interface ExportOptions {
		fileName?: string;
		autoEmbedFonts?: boolean;
		fonts?: Array<{ name: string; url: string }>;
		skipDownload?: boolean;
		svgAsVector?: boolean;
		listConfig?: {
			color?: string;
			spacing?: { before?: number; after?: number };
		};
	}

	export function exportToPptx(
		elementOrSelector: string | HTMLElement | Array<string | HTMLElement>,
		options?: ExportOptions
	): Promise<Blob>;
}
