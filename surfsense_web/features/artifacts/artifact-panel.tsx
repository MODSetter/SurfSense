"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { Dot, FileWarning, RefreshCw, XIcon } from "lucide-react";
import { useState } from "react";
import { artifactPanelAtom, closeArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useMediaQuery } from "@/hooks/use-media-query";
import { ArtifactDownloadButton } from "./artifact-download-button";
import { artifactManifestQueryOptions } from "./artifact-query";
import { artifactDownloadPath } from "./download-file";
import { cannotPreviewMessage, extension } from "./file-format";
import type { ArtifactManifest } from "./model";
import { UnviewableArtifact } from "./unviewable-artifact";
import { VIEWERS } from "./viewer-registry";

function artifactFilename(manifest: ArtifactManifest | undefined): string | null {
	if (!manifest) return null;
	const primary = manifest.files.find((file) => file.role === "primary");
	return primary?.filename ?? `${manifest.title}.md`;
}

export function ArtifactViewerContent({
	artifactId,
	onClose,
}: {
	artifactId: number;
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
		...artifactManifestQueryOptions(workspaceId, artifactId),
		enabled: workspaceIsValid,
	});
	const downloadFilename = artifactFilename(content);
	const primary = content?.files.find((file) => file.role === "primary");
	const artifactType = primary?.filename ?? (content ? "Markdown" : undefined);
	const [zoomControlsContainer, setZoomControlsContainer] = useState<HTMLDivElement | null>(null);

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
									{primary ? extension(primary.filename) : artifactType}
								</span>
							</>
						) : null}
					</div>
					<div className="flex items-center gap-1">
						<div ref={setZoomControlsContainer} className="flex items-center gap-1" />
						{downloadFilename ? (
							<>
								<ArtifactDownloadButton
									path={artifactDownloadPath(workspaceId, artifactId)}
									filename={downloadFilename}
									className="size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
								/>
								<Separator
									orientation="vertical"
									className="mx-1.5 hidden bg-muted-foreground/20 data-[orientation=vertical]:h-4 data-[orientation=vertical]:w-px dark:bg-muted-foreground/25 lg:block"
								/>
							</>
						) : null}
						<Button
							variant="ghost"
							size="icon"
							onClick={onClose}
							className="hidden size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground lg:inline-flex"
						>
							<XIcon className="size-4" />
							<span className="sr-only">Close artifact viewer</span>
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
				) : content && !primary ? (
					<div className="h-full overflow-y-auto px-5 py-4">
						<MarkdownViewer
							content={content.markdown_representation}
							className="mx-auto max-w-3xl"
						/>
					</div>
				) : content ? (
					<FileArtifact content={content} zoomControlsContainer={zoomControlsContainer} />
				) : null}
			</div>
		</div>
	);
}

/** Vaul artifact drawer for viewports where the desktop right panel is unavailable. */
export function MobileArtifactDrawer() {
	const panelState = useAtomValue(artifactPanelAtom);
	const closePanel = useSetAtom(closeArtifactPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (isDesktop || !panelState.isOpen || !panelState.artifactId) return null;

	return (
		<Drawer
			open={panelState.isOpen}
			onOpenChange={(open) => {
				if (!open) closePanel();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="h-[90vh] max-h-[90vh] z-80 overflow-hidden bg-sidebar"
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">Artifact</DrawerTitle>
				<div className="flex min-h-0 flex-1 flex-col overflow-hidden">
					<ArtifactViewerContent artifactId={panelState.artifactId} onClose={closePanel} />
				</div>
			</DrawerContent>
		</Drawer>
	);
}

function FileArtifact({
	content,
	zoomControlsContainer,
}: {
	content: ArtifactManifest;
	zoomControlsContainer: HTMLElement | null;
}) {
	const primary = content.files.find((file) => file.role === "primary");
	if (!primary) {
		return <UnviewableArtifact message="This artifact has no primary file." />;
	}
	const Viewer = VIEWERS[primary.mime_type];
	return Viewer ? (
		<Viewer primary={primary} files={content.files} zoomControlsContainer={zoomControlsContainer} />
	) : (
		<UnviewableArtifact message={cannotPreviewMessage(primary.filename)} />
	);
}
