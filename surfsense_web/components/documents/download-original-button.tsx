"use client";

import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";

interface DownloadOriginalButtonProps {
	documentId: number;
}

/** Renders only when the document has a stored ORIGINAL file; downloads it on click. */
export function DownloadOriginalButton({ documentId }: DownloadOriginalButtonProps) {
	const [originalFilename, setOriginalFilename] = useState<string | null>(null);
	const [downloading, setDownloading] = useState(false);

	useEffect(() => {
		let active = true;
		documentsApiService
			.getDocumentFiles(documentId)
			.then((files) => {
				if (!active) return;
				const original = files.find((file) => file.kind === "ORIGINAL");
				setOriginalFilename(original?.original_filename ?? null);
			})
			.catch(() => {
				if (active) setOriginalFilename(null);
			});
		return () => {
			active = false;
		};
	}, [documentId]);

	if (!originalFilename) return null;

	const handleDownload = async () => {
		setDownloading(true);
		try {
			const response = await authenticatedFetch(
				buildBackendUrl(`/api/v1/documents/${documentId}/download-original`),
				{ method: "GET" }
			);
			if (!response.ok) throw new Error("Download failed");

			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement("a");
			anchor.href = url;
			anchor.download = originalFilename;
			document.body.appendChild(anchor);
			anchor.click();
			anchor.remove();
			URL.revokeObjectURL(url);
			toast.success("Download started");
		} catch {
			toast.error("Failed to download original file");
		} finally {
			setDownloading(false);
		}
	};

	return (
		<Button
			variant="ghost"
			size="icon"
			className="size-6"
			onClick={handleDownload}
			disabled={downloading}
			title={`Download original (${originalFilename})`}
		>
			{downloading ? <Spinner size="xs" /> : <Download className="size-3.5" />}
			<span className="sr-only">Download original file</span>
		</Button>
	);
}
