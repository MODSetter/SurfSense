"use client";

import { Download, File } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import type { ArtifactFile } from "./model";

function humanSize(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function extension(filename: string): string {
	const value = filename.split(".").pop();
	return value && value !== filename ? value.toUpperCase() : "FILE";
}

export function FileDownloadCard({ file }: { file: ArtifactFile }) {
	const [downloading, setDownloading] = useState(false);

	const download = async () => {
		setDownloading(true);
		try {
			const response = await authenticatedFetch(buildBackendUrl(file.content_url));
			if (!response.ok) throw new Error("Download failed");
			const url = URL.createObjectURL(await response.blob());
			const anchor = document.createElement("a");
			anchor.href = url;
			anchor.download = file.filename;
			document.body.appendChild(anchor);
			anchor.click();
			anchor.remove();
			URL.revokeObjectURL(url);
		} catch {
			toast.error("Could not download this artifact");
		} finally {
			setDownloading(false);
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-md flex-col gap-5 rounded-xl border bg-card p-6">
			<div className="flex items-center gap-4">
				<div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
					<File className="size-6" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="truncate text-sm font-medium text-foreground">{file.filename}</p>
					<div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
						<span className="rounded border px-1.5 py-0.5 font-medium">
							{extension(file.filename)}
						</span>
						<span>{humanSize(file.size_bytes)}</span>
					</div>
				</div>
			</div>
			<Button onClick={download} disabled={downloading} className="w-full">
				{downloading ? <Spinner size="sm" /> : <Download className="size-4" />}
				Download
			</Button>
		</div>
	);
}
