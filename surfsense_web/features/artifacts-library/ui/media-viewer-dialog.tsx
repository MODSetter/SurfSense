"use client";

import dynamic from "next/dynamic";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { normalizeArtifactFormat } from "@/features/artifacts/artifact-format-meta";
import { cn } from "@/lib/utils";
import type { LibraryArtifact } from "../model/artifact";
import { LibraryImageViewer } from "./library-image-viewer";

const ViewerFallback = () => (
	<div className="flex items-center justify-center py-12">
		<Spinner />
	</div>
);

const PodcastPlayer = dynamic(
	() => import("@/components/tool-ui/podcast/player").then((m) => m.PodcastPlayer),
	{ ssr: false, loading: ViewerFallback }
);

const VideoPresentationViewer = dynamic(
	() => import("@/components/tool-ui/video-presentation").then((m) => m.VideoPresentationViewer),
	{ ssr: false, loading: ViewerFallback }
);

function dialogLayout(format: string): { width: string; stretch: boolean } {
	if (format === "video") return { width: "max-w-4xl", stretch: true };
	if (format === "podcast") return { width: "max-w-2xl", stretch: true };
	return { width: "max-w-2xl", stretch: false };
}

function MediaViewerBody({
	artifact,
	workspaceId,
}: {
	artifact: LibraryArtifact;
	workspaceId: number;
}) {
	const format = normalizeArtifactFormat(artifact.format);
	if (format === "podcast") {
		if (artifact.artifactId != null) {
			return (
				<PodcastPlayer
					artifactId={artifact.artifactId}
					workspaceId={workspaceId}
					podcastId={artifact.legacyEntityId}
					title={artifact.title}
				/>
			);
		}
		return <PodcastPlayer podcastId={artifact.entityId} title={artifact.title} />;
	}
	if (format === "video") {
		if (artifact.artifactId != null) {
			return (
				<VideoPresentationViewer
					artifactId={artifact.artifactId}
					workspaceId={workspaceId}
					title={artifact.title}
				/>
			);
		}
		return <VideoPresentationViewer presentationId={artifact.entityId} title={artifact.title} />;
	}
	if (artifact.artifactId == null) {
		return (
			<p className="px-6 py-10 text-center text-sm text-muted-foreground">Image not available</p>
		);
	}
	return (
		<LibraryImageViewer
			artifactId={artifact.artifactId}
			workspaceId={workspaceId}
			prompt={artifact.title}
		/>
	);
}

/**
 * Modal viewer for inline-media artifacts (podcast, video, image). Reports and
 * resumes use the shared report panel instead and never reach this dialog.
 */
export function MediaViewerDialog({
	artifact,
	workspaceId,
	onClose,
}: {
	artifact: LibraryArtifact | null;
	workspaceId: number;
	onClose: () => void;
}) {
	const layout = artifact ? dialogLayout(normalizeArtifactFormat(artifact.format)) : null;

	return (
		<Dialog
			open={artifact !== null}
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent
				className={cn(
					// pt-12 keeps content clear of the absolute top-right close button.
					"flex max-h-[88vh] w-[95vw] flex-col overflow-y-auto pt-12",
					layout?.width ?? "max-w-2xl"
				)}
			>
				<DialogTitle className="sr-only">{artifact?.title ?? "Artifact"}</DialogTitle>
				{artifact ? (
					<div
						className={cn(
							layout?.stretch
								? "w-full [&>div]:!my-0 [&>div]:!max-w-none [&>div>*]:!max-w-none"
								: "flex justify-center"
						)}
					>
						<MediaViewerBody artifact={artifact} workspaceId={workspaceId} />
					</div>
				) : null}
			</DialogContent>
		</Dialog>
	);
}
