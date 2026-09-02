"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { downloadArtifactFile } from "@/features/artifacts/api/artifact-download";

export function ArtifactDownloadButton({
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
			await downloadArtifactFile(path, filename);
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
