"use client";

import { Mp4VideoPlayer } from "@/components/tool-ui/video-presentation/mp4-player";
import { buildBackendUrl } from "@/lib/env-config";
import type { FileViewerProps } from "./model";

export default function Mp4FileViewer({ primary }: FileViewerProps) {
	return (
		<div className="flex h-full items-center bg-black">
			<Mp4VideoPlayer src={buildBackendUrl(primary.content_url)} />
		</div>
	);
}
