export function extension(filename: string): string {
	const value = filename.split(".").pop();
	return value && value !== filename ? value.toUpperCase() : "FILE";
}
