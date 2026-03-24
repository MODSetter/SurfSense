export function getVideoDownloadErrorToast(err: unknown): { title: string; description: string } {
	const msg = err instanceof Error ? err.message.toLowerCase() : "";

	if (
		msg.includes("webcodecs") ||
		msg.includes("canrendermediaonweb") ||
		msg.includes("not support")
	) {
		return {
			title: "Browser Not Supported",
			description: "Video rendering requires Chrome, Edge, or Firefox 130+.",
		};
	}

	if (msg.includes("memory") || msg.includes("oom") || msg.includes("allocation")) {
		return {
			title: "Out of Memory",
			description: "The presentation is too large to render. Try closing other tabs.",
		};
	}

	return {
		title: "Download Failed",
		description: "Something went wrong while rendering. Please try again.",
	};
}

export function getPptxExportErrorToast(err: unknown): { title: string; description: string } {
	const msg = err instanceof Error ? err.message.toLowerCase() : "";

	if (
		msg.includes("dynamically imported") ||
		msg.includes("failed to fetch") ||
		msg.includes("network")
	) {
		return {
			title: "Export Unavailable",
			description: "Could not load the export module. Check your network and try again.",
		};
	}

	return {
		title: "PPTX Export Failed",
		description: "Something went wrong while exporting. Please try again.",
	};
}
