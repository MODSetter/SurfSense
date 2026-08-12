export function extension(filename: string): string {
	const value = filename.split(".").pop();
	return value && value !== filename ? value.toUpperCase() : "FILE";
}

export function cannotPreviewMessage(filename: string): string {
	return `${extension(filename)} files can't be previewed here. Download it to open it.`;
}
