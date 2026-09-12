"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { Dot, FileWarning, TriangleAlert, XIcon } from "lucide-react";
import { useState } from "react";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { artifactDownloadPath } from "@/features/artifacts/api/artifact-download-path";
import { artifactManifestQueryOptions } from "@/features/artifacts/api/artifact-queries";
import { getArtifactFormatMeta } from "@/features/artifacts/lib/artifact-format-catalog";
import { artifactDownloadFilename } from "@/features/artifacts/lib/artifact-selectors";
import {
	ArtifactRenderer,
	resolveArtifactPresentation,
} from "@/features/artifacts/rendering/artifact-renderer";
import {
	artifactPanelAtom,
	closeArtifactPanelAtom,
} from "@/features/artifacts/state/artifact-panel.atom";
import { extension } from "@/features/file-viewers/file-format";
import { useMediaQuery } from "@/hooks/use-media-query";
import { ArtifactDownloadButton } from "./artifact-download-button";

function ArtifactRefreshWarning({
	isRefreshing,
	onRetry,
}: {
	isRefreshing: boolean;
	onRetry: () => void;
}) {
	return (
		<div className="pointer-events-none absolute inset-x-0 top-3 z-20 flex justify-center px-3">
			<Alert
				variant="warning"
				className="pointer-events-auto w-fit max-w-full select-none items-center gap-x-2 border-0 bg-[oklch(0.32_0_0)] py-3 text-white shadow-[0_8px_32px_rgb(0_0_0/0.24),0_0_14px_rgb(0_0_0/0.12)] has-[>svg]:grid-cols-[auto_minmax(0,1fr)_auto] *:data-[slot=alert-description]:text-white [&>svg]:text-highlight sm:max-w-lg"
			>
				<TriangleAlert aria-hidden />
				<AlertDescription className="col-start-2 block min-w-0 text-xs sm:text-sm">
					Couldn't refresh this artifact. Showing the last loaded version.
				</AlertDescription>
				<Button
					variant="outline"
					size="sm"
					className="relative col-start-3 h-7 shrink-0 border-0 bg-white px-2.5 text-black hover:bg-white/90 hover:text-black dark:bg-white dark:text-black dark:hover:bg-white/90 dark:hover:text-black"
					disabled={isRefreshing}
					onClick={onRetry}
				>
					<span className={isRefreshing ? "opacity-0" : ""}>Retry</span>
					{isRefreshing ? <Spinner size="sm" className="absolute" /> : null}
				</Button>
			</Alert>
		</div>
	);
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
		isLoadingError,
		isRefetchError,
		isFetching,
		refetch,
	} = useQuery({
		...artifactManifestQueryOptions(workspaceId, artifactId),
		enabled: workspaceIsValid,
	});
	const resolved = content ? resolveArtifactPresentation(content) : null;
	const downloadFilename = artifactDownloadFilename(content, artifactId);
	const artifactType =
		content && resolved?.resolution.kind === "semantic"
			? getArtifactFormatMeta(content.format).detailLabel
			: resolved?.primary
				? extension(resolved.primary.filename)
				: content
					? "Markdown"
					: undefined;
	const [zoomControlsContainer, setZoomControlsContainer] = useState<HTMLDivElement | null>(null);
	const Actions = resolved?.renderer.Actions;

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
								<span className="shrink-0 text-xs text-muted-foreground">{artifactType}</span>
							</>
						) : null}
					</div>
					<div className="flex items-center gap-1">
						<div ref={setZoomControlsContainer} className="flex items-center gap-1" />
						{workspaceIsValid ? (
							<>
								{Actions && content ? (
									<Actions workspaceId={workspaceId} manifest={content} />
								) : null}
								{resolved?.renderer.downloadable ? (
									<ArtifactDownloadButton
										path={artifactDownloadPath(workspaceId, artifactId)}
										filename={downloadFilename}
										className="size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
									/>
								) : null}
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

			<div className="relative min-h-0 flex-1 overflow-hidden" aria-busy={loading || isFetching}>
				{isRefetchError ? (
					<ArtifactRefreshWarning isRefreshing={isFetching} onRetry={() => void refetch()} />
				) : null}

				{loading ? (
					<div className="flex h-full items-center justify-center px-5 py-4">
						<Spinner size="lg" />
					</div>
				) : isLoadingError ? (
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
						<Button variant="secondary" size="sm" onClick={() => void refetch()}>
							Try again
						</Button>
					</div>
				) : content ? (
					<ArtifactRenderer
						workspaceId={workspaceId}
						manifest={content}
						zoomControlsContainer={zoomControlsContainer}
						presentation={resolved ?? undefined}
					/>
				) : null}
			</div>
		</div>
	);
}

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
