import { extension } from "@/features/file-viewers/file-format";

export const MINDMAP_FILE_SUFFIX = ".mindmap.png";

export function artifactFormatFromFilename(filename: string): string {
	return filename.toLowerCase().endsWith(MINDMAP_FILE_SUFFIX) ? "mindmap" : extension(filename);
}

export function artifactDownloadFilename(title: string, format: string): string {
	if (format.trim().toLowerCase() === "mindmap") {
		const filename = title.toLowerCase().endsWith(MINDMAP_FILE_SUFFIX)
			? title.slice(0, -MINDMAP_FILE_SUFFIX.length)
			: title;
		return filename.toLowerCase().endsWith(".png") ? filename : `${filename}.png`;
	}
	const suffix = `.${format}`;
	return title.toLowerCase().endsWith(suffix.toLowerCase()) ? title : `${title}${suffix}`;
}
