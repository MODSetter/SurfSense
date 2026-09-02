import { useAtomValue, useSetAtom } from "jotai";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { artifactDownloadPath } from "@/features/artifacts/api/artifact-download-path";
import { isArtifactDownloadable } from "@/features/artifacts/lib/artifact-format-catalog";
import { openArtifactPanelAtom } from "@/features/artifacts/state/artifact-panel.atom";
import { ArtifactDownloadButton } from "@/features/artifacts/ui/artifact-download-button";
import { ArtifactFormatIcon } from "@/features/artifacts/ui/artifact-format-icon";
import { ArtifactFormatLabel } from "@/features/artifacts/ui/artifact-format-label";
import { useMediaQuery } from "@/hooks/use-media-query";
import { openChatArtifact } from "../lib/open-chat-artifact";
import type { ChatArtifact } from "../model/artifact";
import { closeArtifactsPanelAtom } from "../state/artifacts-panel.atom";

export function ArtifactRow({ artifact }: { artifact: ChatArtifact }) {
	const openArtifactPanel = useSetAtom(openArtifactPanelAtom);
	const closeArtifactsPanel = useSetAtom(closeArtifactsPanelAtom);
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const canOpen = artifact.artifactId != null;
	const canDownload =
		canOpen &&
		Number.isFinite(workspaceId) &&
		workspaceId > 0 &&
		isArtifactDownloadable(artifact.format);

	const handleOpen = () => {
		const artifactId = artifact.artifactId;
		if (artifactId == null) return;
		void openChatArtifact({ ...artifact, artifactId }, "in-chat", {
			closeArtifactsPanel,
			isDesktop,
			openArtifactPanel,
		});
	};

	return (
		<div className="group relative flex min-h-20 w-full items-center gap-3 rounded-xl border bg-muted/30 px-3 py-3 text-left transition-colors hover:bg-accent hover:text-accent-foreground">
			<button
				type="button"
				disabled={!canOpen}
				onClick={handleOpen}
				className="absolute inset-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default"
			>
				<span className="sr-only">
					{canOpen ? `Open ${artifact.title}` : `${artifact.title} metadata is loading`}
				</span>
			</button>
			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
				<ArtifactFormatIcon format={artifact.format} className="size-4" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{artifact.title}</span>
				{artifact.metadataStatus === "pending" ? (
					<TextShimmerLoader text="Loading metadata" size="sm" className="mt-0.5 block" />
				) : (
					<ArtifactFormatLabel
						format={artifact.format}
						className="mt-0.5 text-xs text-muted-foreground"
					/>
				)}
			</span>
			{canDownload && artifact.artifactId != null ? (
				<ArtifactDownloadButton
					path={artifactDownloadPath(workspaceId, artifact.artifactId)}
					filename={artifact.title}
					className="relative z-10 size-9 shrink-0 text-muted-foreground hover:text-foreground"
				/>
			) : null}
		</div>
	);
}
