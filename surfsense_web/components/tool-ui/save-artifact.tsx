"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { FileText } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { z } from "zod";
import { openArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { ArtifactDownloadButton } from "@/features/artifacts/artifact-download-button";
import { artifactQueryKey, artifactQueryOptions } from "@/features/artifacts/artifact-query";
import { artifactDownloadPath } from "@/features/artifacts/download-file";
import { extension } from "@/features/artifacts/file-format";
import { useMediaQuery } from "@/hooks/use-media-query";

const SaveArtifactArgsSchema = z.object({
	title: z.string(),
	content: z.string().nullish(),
	markdown_representation: z.string().nullish(),
	path: z.string().nullish(),
	preview_path: z.string().nullish(),
	description: z.string().nullish(),
	document_id: z.number().nullish(),
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
	document_id: z.number().nullish(),
	title: z.string().nullish(),
	files: z.array(ArtifactFileSchema).optional(),
	error: z.string().nullish(),
});

type SaveArtifactArgs = z.infer<typeof SaveArtifactArgsSchema>;
type SaveArtifactResult = z.infer<typeof SaveArtifactResultSchema>;

function ArtifactPending({ title }: { title: string }) {
	return (
		<div className="my-4 max-w-lg rounded-xl border bg-muted/30 px-5 py-4">
			<p className="text-sm font-semibold">{title}</p>
			<TextShimmerLoader text="Saving artifact" size="sm" />
		</div>
	);
}

function ArtifactError({ title, error }: { title: string; error: string }) {
	return (
		<div role="alert" className="my-4 max-w-lg rounded-xl border bg-muted/30 px-5 py-4">
			<p className="text-sm font-semibold text-destructive">Artifact save failed</p>
			<p className="mt-1 text-sm text-foreground">{title}</p>
			<p className="mt-1 text-xs text-muted-foreground">{error}</p>
		</div>
	);
}

function ArtifactCard({
	documentId,
	title,
	autoOpen,
	publicRoute,
}: {
	documentId: number;
	title: string;
	autoOpen: boolean;
	publicRoute: boolean;
}) {
	const openPanel = useSetAtom(openArtifactPanelAtom);
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const isDesktop = useMediaQuery("(min-width: 768px)");
	const openedRef = useRef(false);
	const canDownload = !publicRoute && Number.isFinite(workspaceId) && workspaceId > 0;
	const { data: current } = useQuery({
		...artifactQueryOptions(workspaceId, documentId),
		enabled: canDownload,
	});
	const currentPrimary =
		current?.kind === "file" ? current.files.find((file) => file.role === "primary") : undefined;
	const currentTitle = current?.title ?? title;
	const fileType =
		current?.kind === "text"
			? "Markdown"
			: currentPrimary?.filename
				? extension(currentPrimary.filename)
				: "File";
	const filename =
		current?.kind === "text"
			? `${current.title}.md`
			: (currentPrimary?.filename ?? `${currentTitle}.md`);

	useEffect(() => {
		if (autoOpen && isDesktop && !publicRoute && !openedRef.current) {
			openedRef.current = true;
			openPanel({ documentId });
		}
	}, [autoOpen, documentId, isDesktop, openPanel, publicRoute]);

	return (
		<div className="relative my-4 flex w-full max-w-lg items-center gap-3 rounded-xl border bg-muted/30 p-4 text-left transition-colors hover:bg-accent hover:text-accent-foreground">
			{/* Stretched overlay opens the panel; the download button is a sibling above it,
			    since a button cannot be nested inside another button. */}
			<button
				type="button"
				disabled={publicRoute}
				onClick={() => openPanel({ documentId })}
				className="absolute inset-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none"
			>
				<span className="sr-only">Open {currentTitle}</span>
			</button>

			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
				<FileText className="size-5 text-muted-foreground" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium">{currentTitle}</span>
				<span className="mt-0.5 block truncate text-xs text-muted-foreground">{fileType}</span>
			</span>
			{canDownload ? (
				<ArtifactDownloadButton
					path={artifactDownloadPath(workspaceId, documentId)}
					filename={filename}
					className="relative z-10 size-7 shrink-0 text-muted-foreground"
				/>
			) : null}
		</div>
	);
}

export const SaveArtifactToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<SaveArtifactArgs, SaveArtifactResult>) => {
	const pathname = usePathname();
	const publicRoute = pathname?.startsWith("/public/") ?? false;
	const sawRunningRef = useRef(false);
	const queryClient = useQueryClient();
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const savedDocumentId = result?.status === "saved" ? result.document_id : null;

	useEffect(() => {
		if (
			!sawRunningRef.current ||
			!savedDocumentId ||
			!Number.isFinite(workspaceId) ||
			workspaceId <= 0
		) {
			return;
		}
		void queryClient.invalidateQueries({
			queryKey: artifactQueryKey(workspaceId, savedDocumentId),
		});
	}, [queryClient, savedDocumentId, workspaceId]);

	if (status.type === "running" || status.type === "requires-action") {
		sawRunningRef.current = true;
		return <ArtifactPending title={args.title || "Document"} />;
	}
	if (status.type === "incomplete") {
		return (
			<ArtifactError
				title={args.title || "Document"}
				error={
					status.reason === "cancelled"
						? "Artifact saving was cancelled"
						: typeof status.error === "string"
							? status.error
							: "An error occurred"
				}
			/>
		);
	}
	if (!result) return <ArtifactPending title={args.title || "Document"} />;
	if (result.status === "failed") {
		return (
			<ArtifactError
				title={result.title || args.title || "Document"}
				error={result.error || "The artifact could not be saved"}
			/>
		);
	}
	if (!result.document_id) {
		return <ArtifactError title={args.title || "Document"} error="Missing document ID" />;
	}
	return (
		<ArtifactCard
			documentId={result.document_id}
			title={result.title || args.title || "Document"}
			autoOpen={sawRunningRef.current}
			publicRoute={publicRoute}
		/>
	);
};
