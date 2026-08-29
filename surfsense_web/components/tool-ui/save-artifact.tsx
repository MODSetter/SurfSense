"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { z } from "zod";
import { artifactPanelAtom, openArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { Mp4VideoPlayer } from "@/components/tool-ui/video-presentation/mp4-player";
import { Spinner } from "@/components/ui/spinner";
import { ArtifactDownloadButton } from "@/features/artifacts/artifact-download-button";
import { ArtifactFormatIcon } from "@/features/artifacts/artifact-format-icon";
import { ArtifactFormatLabel } from "@/features/artifacts/artifact-format-label";
import {
	artifactManifestQueryOptions,
	invalidatePublishedArtifact,
} from "@/features/artifacts/artifact-query";
import { artifactDownloadPath } from "@/features/artifacts/download-file";
import { extension } from "@/features/file-viewers/file-format";
import { buildBackendUrl } from "@/lib/env-config";
import { cn } from "@/lib/utils";

const SaveArtifactArgsSchema = z.object({
	title: z.string(),
	artifact_id: z.number().nullish(),
});

const ArtifactFileSchema = z.object({
	file_id: z.number(),
	role: z.enum(["primary", "preview"]),
	filename: z.string(),
	mime_type: z.string(),
	size_bytes: z.number().nonnegative(),
});

const SaveArtifactResultSchema = z.object({
	status: z.enum(["saved", "failed"]),
	artifact_id: z.number().nullish(),
	title: z.string().nullish(),
	files: z.array(ArtifactFileSchema).optional(),
	error: z.string().nullish(),
});

type SaveArtifactArgs = z.infer<typeof SaveArtifactArgsSchema>;
type SaveArtifactResult = z.infer<typeof SaveArtifactResultSchema>;

function ArtifactCard({
	artifactId,
	title,
	format,
	filename,
	publicRoute,
	toolCallId,
}: {
	artifactId: number;
	title: string;
	format: string;
	filename: string;
	publicRoute: boolean;
	toolCallId: string;
}) {
	const openPanel = useSetAtom(openArtifactPanelAtom);
	const panelState = useAtomValue(artifactPanelAtom);
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const canDownload = !publicRoute && Number.isFinite(workspaceId) && workspaceId > 0;
	const selected = panelState.isOpen && panelState.selectedCardToolCallId === toolCallId;

	return (
		<div
			className={cn(
				"relative my-4 flex w-full select-none items-center gap-3 rounded-xl border bg-muted/30 p-4 text-left transition-colors hover:bg-accent hover:text-accent-foreground",
				selected && "ring-1 ring-primary/60"
			)}
		>
			{/* Stretched overlay opens the panel; the download button is a sibling above it,
			    since a button cannot be nested inside another button. */}
			<button
				type="button"
				disabled={publicRoute}
				onClick={() => openPanel({ artifactId, selectedCardToolCallId: toolCallId })}
				className="absolute inset-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none"
			>
				<span className="sr-only">Open {title}</span>
			</button>

			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
				<ArtifactFormatIcon format={format} className="size-5 text-muted-foreground" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium">{title}</span>
				<ArtifactFormatLabel format={format} className="mt-0.5 text-xs text-muted-foreground" />
			</span>
			{canDownload ? (
				<ArtifactDownloadButton
					path={artifactDownloadPath(workspaceId, artifactId)}
					filename={filename}
					appearance="text"
					className="relative z-10 h-9 shrink-0 rounded-md bg-popover px-3 text-sm font-normal text-foreground hover:bg-popover/80"
				/>
			) : null}
		</div>
	);
}

export function Mp4ArtifactCard({
	artifactId,
	title,
	filename,
	workspaceId,
}: {
	artifactId: number;
	title: string;
	filename: string;
	workspaceId: number;
}) {
	const {
		data: manifest,
		error,
		isPending,
	} = useQuery(artifactManifestQueryOptions(workspaceId, artifactId));
	const primary = manifest?.files.find((file) => file.role === "primary");
	const videoSrc = primary?.mime_type === "video/mp4" ? buildBackendUrl(primary.content_url) : null;

	return (
		<div
			className="my-4 w-full select-none overflow-hidden rounded-xl border bg-muted/30"
			aria-busy={isPending}
		>
			<div className="flex items-center gap-3 p-4">
				<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
					<ArtifactFormatIcon format="video" className="size-5 text-muted-foreground" />
				</span>
				<span className="min-w-0 flex-1">
					<span className="block truncate text-sm font-medium">{title}</span>
					<ArtifactFormatLabel format="video" className="mt-0.5 text-xs text-muted-foreground" />
				</span>
				<ArtifactDownloadButton
					path={artifactDownloadPath(workspaceId, artifactId)}
					filename={filename}
					appearance="text"
					className="h-9 shrink-0 rounded-md bg-popover px-3 text-sm font-normal text-foreground hover:bg-popover/80"
				/>
			</div>
			<div className="border-t bg-black">
				{isPending ? (
					<div className="flex aspect-video items-center justify-center">
						<Spinner size="lg" />
					</div>
				) : videoSrc ? (
					<Mp4VideoPlayer src={videoSrc} />
				) : (
					<div
						role="alert"
						className="flex aspect-video items-center justify-center px-5 text-center text-sm text-white/70"
					>
						{error instanceof Error ? error.message : "Video preview is not available"}
					</div>
				)}
			</div>
		</div>
	);
}

export const SaveArtifactToolUI = ({
	args,
	result,
	status,
	toolCallId,
}: ToolCallMessagePartProps<SaveArtifactArgs, SaveArtifactResult>) => {
	const pathname = usePathname();
	const publicRoute = pathname?.startsWith("/public/") ?? false;
	const queryClient = useQueryClient();
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const savedArtifactId = result?.status === "saved" ? result.artifact_id : null;

	useEffect(() => {
		if (!savedArtifactId || !Number.isFinite(workspaceId) || workspaceId <= 0) {
			return;
		}
		void invalidatePublishedArtifact(queryClient, workspaceId, savedArtifactId);
	}, [queryClient, savedArtifactId, workspaceId]);

	if (status.type !== "complete" || result?.status !== "saved" || !result.artifact_id) return null;
	const primary = result.files?.find((file) => file.role === "primary");
	const title = result.title || args.title || "Document";
	const filename = primary?.filename ?? `${title}.md`;
	if (
		primary?.mime_type === "video/mp4" &&
		!publicRoute &&
		Number.isFinite(workspaceId) &&
		workspaceId > 0
	) {
		return (
			<Mp4ArtifactCard
				artifactId={result.artifact_id}
				title={title}
				filename={filename}
				workspaceId={workspaceId}
			/>
		);
	}
	const format = primary?.filename ? extension(primary.filename) : "file";
	return (
		<ArtifactCard
			artifactId={result.artifact_id}
			title={title}
			format={format}
			filename={filename}
			publicRoute={publicRoute}
			toolCallId={toolCallId}
		/>
	);
};
