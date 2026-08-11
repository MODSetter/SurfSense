"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { Dot, FileWarning, RefreshCw, XIcon } from "lucide-react";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ArtifactDownloadButton } from "./artifact-download-button";
import { artifactQueryOptions } from "./artifact-query";
import { artifactDownloadPath } from "./download-file";
import { cannotPreviewMessage, extension } from "./file-format";
import type { ArtifactContent } from "./model";
import { UnviewableArtifact } from "./unviewable-artifact";
import { VIEWERS } from "./viewer-registry";

function artifactFilename(content: ArtifactContent | undefined): string | null {
	if (content?.kind === "file") {
		const primary = content.files.find((file) => file.role === "primary");
		return primary?.filename ?? null;
	}
	if (content?.kind === "text") {
		return `${content.title}.md`;
	}
	return null;
}

export function ArtifactPanelContent({
	documentId,
	onClose,
}: {
	documentId: number;
	onClose: () => void;
}) {
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const workspaceIsValid = Number.isFinite(workspaceId) && workspaceId > 0;
	const {
		data: content,
		error,
		isPending: loading,
		refetch,
	} = useQuery({
		...artifactQueryOptions(workspaceId, documentId),
		enabled: workspaceIsValid,
	});
	const downloadFilename = artifactFilename(content);
	const artifactType =
		content?.kind === "text"
			? "Markdown"
			: content?.files.find((file) => file.role === "primary")?.filename;

	return (
		<div className="flex h-full min-h-0 flex-col">
			<div className="shrink-0">
				<div className="grid h-12 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-4">
					<div className="flex min-w-0 items-center">
						<p className="truncate text-sm text-muted-foreground">
							{content?.title ?? (loading ? "Loading…" : "Artifact")}
						</p>
						{artifactType ? (
							<>
								<Dot className="size-4 shrink-0 text-muted-foreground/60" aria-hidden="true" />
								<span className="shrink-0 text-xs text-muted-foreground">
									{content?.kind === "text" ? artifactType : extension(artifactType)}
								</span>
							</>
						) : null}
					</div>
					<div className="flex items-center gap-1">
						{downloadFilename ? (
							<>
								<ArtifactDownloadButton
									path={artifactDownloadPath(workspaceId, documentId)}
									filename={downloadFilename}
									className="size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
								/>
								<Separator
									orientation="vertical"
									className="mx-1.5 bg-muted-foreground/20 data-[orientation=vertical]:h-4 data-[orientation=vertical]:w-px dark:bg-muted-foreground/25"
								/>
							</>
						) : null}
						<Button
							variant="ghost"
							size="icon"
							onClick={onClose}
							className="size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
						>
							<XIcon className="size-4" />
							<span className="sr-only">Close artifact panel</span>
						</Button>
					</div>
				</div>
			</div>

			{/* Viewers fill the panel edge to edge; everything else scrolls with padding. */}
			<div className="min-h-0 flex-1 overflow-hidden" aria-busy={loading}>
				{loading ? (
					<div className="h-full space-y-3 px-5 py-4">
						<Skeleton className="h-7 w-2/3" />
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-5/6" />
						<Skeleton className="h-4 w-4/6" />
					</div>
				) : error ? (
					<div
						role="alert"
						className="flex h-full flex-col items-center justify-center gap-3 px-5 py-4 text-center"
					>
						<FileWarning className="size-8 text-muted-foreground" />
						<div>
							<p className="text-sm font-medium">Couldn&apos;t open this artifact</p>
							<p className="mt-1 text-xs text-muted-foreground">
								{error instanceof Error ? error.message : "Artifact could not be loaded"}
							</p>
						</div>
						<Button variant="outline" size="sm" onClick={() => void refetch()}>
							<RefreshCw className="size-4" />
							Try again
						</Button>
					</div>
				) : content?.kind === "text" ? (
					<div className="h-full overflow-y-auto px-5 py-4">
						<MarkdownViewer content={content.source_markdown} className="mx-auto max-w-3xl" />
					</div>
				) : content?.kind === "file" ? (
					<FileArtifact content={content} />
				) : null}
			</div>
		</div>
	);
}

function FileArtifact({ content }: { content: Extract<ArtifactContent, { kind: "file" }> }) {
	const primary = content.files.find((file) => file.role === "primary");
	if (!primary) {
		return <UnviewableArtifact message="This artifact has no primary file." />;
	}
	const Viewer = VIEWERS[primary.mime_type];
	return Viewer ? (
		<Viewer primary={primary} files={content.files} />
	) : (
		<UnviewableArtifact message={cannotPreviewMessage(primary.filename)} />
	);
}
