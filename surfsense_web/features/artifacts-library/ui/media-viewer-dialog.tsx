"use client";

import dynamic from "next/dynamic";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { LibraryArtifact, LibraryArtifactKind } from "../model/artifact";
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

function dialogLayout(kind: LibraryArtifactKind): { width: string; stretch: boolean } {
	if (kind === "video") return { width: "max-w-4xl", stretch: true };
	if (kind === "podcast") return { width: "max-w-2xl", stretch: true };
	return { width: "max-w-2xl", stretch: false };
}

function MediaViewerBody({
	artifact,
	workspaceId,
}: {
	artifact: LibraryArtifact;
	workspaceId: number;
}) {
	if (artifact.kind === "podcast") {
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
	if (artifact.kind === "video") {
		if (artifact.artifactId == null) {
			return (
				<p className="px-6 py-10 text-center text-sm text-muted-foreground">
					Video not available
				</p>
			);
		}
		return (
			<VideoPresentationViewer
				artifactId={artifact.artifactId}
				workspaceId={workspaceId}
				title={artifact.title}
			/>
		);
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
	const layout = artifact ? dialogLayout(artifact.kind) : null;

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
