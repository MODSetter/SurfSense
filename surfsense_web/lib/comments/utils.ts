export function convertRenderedToDisplay(contentRendered: string): string {
	// Convert @{DisplayName} format to @DisplayName for editing
	return contentRendered.replace(/@\{([^}]+)\}/g, "@$1");
}
