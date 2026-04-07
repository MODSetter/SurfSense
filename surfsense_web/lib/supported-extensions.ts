const audioFileTypes: Record<string, string[]> = {
	"audio/mpeg": [".mp3", ".mpeg", ".mpga"],
	"audio/mp4": [".mp4", ".m4a"],
	"audio/wav": [".wav"],
	"audio/webm": [".webm"],
	"text/markdown": [".md", ".markdown"],
	"text/plain": [".txt"],
};

const commonTypes: Record<string, string[]> = {
	"application/pdf": [".pdf"],
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
	"application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
	"text/html": [".html", ".htm"],
	"text/csv": [".csv"],
	"text/tab-separated-values": [".tsv"],
	"image/jpeg": [".jpg", ".jpeg"],
	"image/png": [".png"],
	"image/bmp": [".bmp"],
	"image/webp": [".webp"],
	"image/tiff": [".tiff"],
};

export const FILE_TYPE_CONFIG: Record<string, Record<string, string[]>> = {
	LLAMACLOUD: {
		...commonTypes,
		"application/msword": [".doc"],
		"application/vnd.ms-word.document.macroEnabled.12": [".docm"],
		"application/msword-template": [".dot"],
		"application/vnd.ms-word.template.macroEnabled.12": [".dotm"],
		"application/vnd.ms-powerpoint": [".ppt"],
		"application/vnd.ms-powerpoint.template.macroEnabled.12": [".pptm"],
		"application/vnd.ms-powerpoint.template": [".pot"],
		"application/vnd.openxmlformats-officedocument.presentationml.template": [".potx"],
		"application/vnd.ms-excel": [".xls"],
		"application/vnd.ms-excel.sheet.macroEnabled.12": [".xlsm"],
		"application/vnd.ms-excel.sheet.binary.macroEnabled.12": [".xlsb"],
		"application/vnd.ms-excel.workspace": [".xlw"],
		"application/rtf": [".rtf"],
		"application/xml": [".xml"],
		"application/epub+zip": [".epub"],
		"image/gif": [".gif"],
		"image/svg+xml": [".svg"],
		...audioFileTypes,
	},
	DOCLING: {
		...commonTypes,
		"text/asciidoc": [".adoc", ".asciidoc"],
		"text/html": [".html", ".htm", ".xhtml"],
		"image/tiff": [".tiff", ".tif"],
		...audioFileTypes,
	},
	AZURE_DI: {
		...commonTypes,
		"image/heic": [".heic"],
		...audioFileTypes,
	},
	default: {
		...commonTypes,
		"application/msword": [".doc"],
		"message/rfc822": [".eml"],
		"application/epub+zip": [".epub"],
		"image/heic": [".heic"],
		"application/vnd.ms-outlook": [".msg"],
		"application/vnd.oasis.opendocument.text": [".odt"],
		"text/x-org": [".org"],
		"application/pkcs7-signature": [".p7s"],
		"application/vnd.ms-powerpoint": [".ppt"],
		"text/x-rst": [".rst"],
		"application/rtf": [".rtf"],
		"application/vnd.ms-excel": [".xls"],
		"application/xml": [".xml"],
		...audioFileTypes,
	},
};

export function getAcceptedFileTypes(): Record<string, string[]> {
	const etlService = process.env.NEXT_PUBLIC_ETL_SERVICE;
	return FILE_TYPE_CONFIG[etlService || "default"] || FILE_TYPE_CONFIG.default;
}

export function getSupportedExtensions(
	acceptedFileTypes?: Record<string, string[]>
): string[] {
	const types = acceptedFileTypes ?? getAcceptedFileTypes();
	return Array.from(new Set(Object.values(types).flat())).sort();
}

export function getSupportedExtensionsSet(
	acceptedFileTypes?: Record<string, string[]>
): Set<string> {
	return new Set(getSupportedExtensions(acceptedFileTypes).map((ext) => ext.toLowerCase()));
}
