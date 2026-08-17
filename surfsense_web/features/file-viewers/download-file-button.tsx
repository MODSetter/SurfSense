"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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

async function downloadFile(path: string, filename: string): Promise<void> {
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
}

export function DownloadFileButton({
	path,
	filename,
	className,
	appearance = "icon",
}: {
	path: string;
	filename: string;
	className?: string;
	appearance?: "icon" | "text";
}) {
	const [downloading, setDownloading] = useState(false);

	const handleClick = async () => {
		setDownloading(true);
		try {
			await downloadFile(path, filename);
		} catch {
			toast.error("Could not download this file");
		} finally {
			setDownloading(false);
		}
	};

	return (
		<Button
			type="button"
			variant="ghost"
			size={appearance === "icon" ? "icon" : "sm"}
			className={className}
			disabled={downloading}
			onClick={handleClick}
		>
			{appearance === "text" ? (
				"Download"
			) : (
				<>
					<Download className="size-4" />
					<span className="sr-only">Download {filename}</span>
				</>
			)}
		</Button>
	);
}
