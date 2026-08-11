"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { downloadArtifactFile } from "./download-file";

export function ArtifactDownloadButton({
	path,
	filename,
	className,
}: {
	path: string;
	filename: string;
	className?: string;
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
			size="icon"
			className={className}
			disabled={downloading}
			onClick={handleClick}
		>
			{downloading ? <Spinner size="sm" /> : <Download className="size-4" />}
			<span className="sr-only">Download {filename}</span>
		</Button>
	);
}
