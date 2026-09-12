import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

function responseFilename(disposition: string | null): string | null {
	if (!disposition) return null;
	let fallback: string | null = null;
	for (const part of disposition.split(";").slice(1)) {
		const separator = part.indexOf("=");
		if (separator < 0) continue;
		const name = part.slice(0, separator).trim().toLowerCase();
		const value = part.slice(separator + 1).trim();
		if (name === "filename*") {
			const encoded = value.toLowerCase().startsWith("utf-8''") ? value.slice(7) : value;
			try {
				return decodeURIComponent(encoded);
			} catch {
				continue;
			}
		}
		if (name === "filename") {
			fallback = value.startsWith('"') && value.endsWith('"') ? value.slice(1, -1) : value;
		}
	}
	return fallback;
}

// Authenticated bytes must be handed to the browser rather than linked directly.
export async function downloadArtifactFile(path: string, filename: string): Promise<void> {
	try {
		const response = await authenticatedFetch(buildBackendUrl(path));
		if (!response.ok) throw new Error("Download failed");
		const url = URL.createObjectURL(await response.blob());
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = responseFilename(response.headers.get("content-disposition")) ?? filename;
		document.body.appendChild(anchor);
		anchor.click();
		anchor.remove();
		URL.revokeObjectURL(url);
	} catch {
		toast.error("Could not download this artifact");
	}
}
