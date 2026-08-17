"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { z } from "zod";
import { artifactPanelAtom, openArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { ArtifactDownloadButton } from "@/features/artifacts/artifact-download-button";
import { ArtifactFormatIcon } from "@/features/artifacts/artifact-format-icon";
import { ArtifactFormatLabel } from "@/features/artifacts/artifact-format-label";
import {
	artifactListQueryKey,
	artifactManifestQueryKey,
} from "@/features/artifacts/artifact-query";
import { artifactDownloadPath } from "@/features/artifacts/download-file";
import { extension } from "@/features/file-viewers/file-format";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

const SaveArtifactArgsSchema = z.object({
	title: z.string(),
	content: z.string().nullish(),
	markdown_representation: z.string().nullish(),
	path: z.string().nullish(),
	preview_path: z.string().nullish(),
	description: z.string().nullish(),
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

function ArtifactPending({ title, format }: { title: string; format: string }) {
	return (
		<div
			aria-busy="true"
			className="my-4 flex w-full items-center gap-3 rounded-xl border bg-muted/30 p-4"
		>
			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
				<ArtifactFormatIcon format={format} className="size-5 text-muted-foreground" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium">{title}</span>
				<TextShimmerLoader text="Saving artifact" size="sm" className="mt-0.5 block" />
			</span>
		</div>
	);
}

function ArtifactError({
	title,
	format,
	message,
}: {
	title: string;
	format: string;
	message: string;
}) {
	return (
		<div
			role="alert"
			className="my-4 flex w-full items-center gap-3 rounded-xl border bg-muted/30 p-4"
		>
			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
				<ArtifactFormatIcon format={format} className="size-5 text-muted-foreground" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{title}</span>
				<span className="mt-0.5 block truncate text-xs text-destructive">{message}</span>
			</span>
		</div>
	);
}

function ArtifactCard({
	artifactId,
	title,
	format,
	filename,
	autoOpen,
	publicRoute,
	toolCallId,
}: {
	artifactId: number;
	title: string;
	format: string;
	filename: string;
	autoOpen: boolean;
	publicRoute: boolean;
	toolCallId: string;
}) {
	const openPanel = useSetAtom(openArtifactPanelAtom);
	const panelState = useAtomValue(artifactPanelAtom);
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const openedRef = useRef(false);
	const canDownload = !publicRoute && Number.isFinite(workspaceId) && workspaceId > 0;
	const selected = panelState.isOpen && panelState.selectedCardToolCallId === toolCallId;

	useEffect(() => {
		if (autoOpen && isDesktop && !publicRoute && !openedRef.current) {
			openedRef.current = true;
			openPanel({ artifactId, selectedCardToolCallId: toolCallId });
		}
	}, [artifactId, autoOpen, isDesktop, openPanel, publicRoute, toolCallId]);

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
				<ArtifactFormatLabel
					format={format}
					className="mt-0.5 text-xs text-muted-foreground"
				/>
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

export const SaveArtifactToolUI = ({
	args,
	result,
	status,
	toolCallId,
}: ToolCallMessagePartProps<SaveArtifactArgs, SaveArtifactResult>) => {
	const pathname = usePathname();
	const publicRoute = pathname?.startsWith("/public/") ?? false;
	const sawRunningRef = useRef(false);
	const queryClient = useQueryClient();
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const savedArtifactId = result?.status === "saved" ? result.artifact_id : null;
	const pendingFormat = args.path ? extension(args.path) : "file";

	useEffect(() => {
		if (
			!sawRunningRef.current ||
			!savedArtifactId ||
			!Number.isFinite(workspaceId) ||
			workspaceId <= 0
		) {
			return;
		}
		void queryClient.invalidateQueries({
			queryKey: artifactManifestQueryKey(workspaceId, savedArtifactId),
		});
		void queryClient.invalidateQueries({ queryKey: artifactListQueryKey(workspaceId) });
		void queryClient.invalidateQueries({ queryKey: ["artifacts-library", workspaceId] });
	}, [queryClient, savedArtifactId, workspaceId]);

	if (status.type === "running" || status.type === "requires-action") {
		sawRunningRef.current = true;
		return <ArtifactPending title={args.title || "Document"} format={pendingFormat} />;
	}
	if (status.type === "incomplete") {
		return (
			<ArtifactError
				title={args.title || "Document"}
				format={pendingFormat}
				message={
					status.reason === "cancelled"
						? "Artifact saving was cancelled"
						: "Artifact save failed"
				}
			/>
		);
	}
	if (!result) return <ArtifactPending title={args.title || "Document"} format={pendingFormat} />;
	if (result.status === "failed") {
		return (
			<ArtifactError
				title={result.title || args.title || "Document"}
				format={pendingFormat}
				message="Artifact save failed"
			/>
		);
	}
	if (!result.artifact_id) {
		return (
			<ArtifactError
				title={args.title || "Document"}
				format={pendingFormat}
				message="Artifact save failed"
			/>
		);
	}
	const primary = result.files?.find((file) => file.role === "primary");
	const format = primary?.filename ? extension(primary.filename) : pendingFormat;
	const title = result.title || args.title || "Document";
	return (
		<ArtifactCard
			artifactId={result.artifact_id}
			title={title}
			format={format}
			filename={primary?.filename ?? `${title}.md`}
			autoOpen={sawRunningRef.current}
			publicRoute={publicRoute}
			toolCallId={toolCallId}
		/>
	);
};
