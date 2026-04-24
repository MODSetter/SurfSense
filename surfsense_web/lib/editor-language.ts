const EXTENSION_TO_MONACO_LANGUAGE: Record<string, string> = {
	css: "css",
	csv: "plaintext",
	cjs: "javascript",
	html: "html",
	htm: "html",
	ini: "ini",
	js: "javascript",
	json: "json",
	markdown: "markdown",
	md: "markdown",
	mjs: "javascript",
	py: "python",
	sql: "sql",
	toml: "plaintext",
	ts: "typescript",
	tsx: "typescript",
	xml: "xml",
	yaml: "yaml",
	yml: "yaml",
};

export function inferMonacoLanguageFromPath(filePath: string | null | undefined): string {
	if (!filePath) return "plaintext";

	const fileName = filePath.split("/").pop() ?? filePath;
	const extensionIndex = fileName.lastIndexOf(".");
	if (extensionIndex <= 0 || extensionIndex === fileName.length - 1) {
		return "plaintext";
	}

	const extension = fileName.slice(extensionIndex + 1).toLowerCase();
	return EXTENSION_TO_MONACO_LANGUAGE[extension] ?? "plaintext";
}
