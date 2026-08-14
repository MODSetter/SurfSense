import { useAtomValue, useSetAtom } from "jotai";
import { openArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { ArtifactDownloadButton } from "@/features/artifacts/artifact-download-button";
import { ArtifactFormatIcon } from "@/features/artifacts/artifact-format-icon";
import { ArtifactFormatLabel } from "@/features/artifacts/artifact-format-label";
import { artifactDownloadPath } from "@/features/artifacts/download-file";
import { useMediaQuery } from "@/hooks/use-media-query";
import { openChatArtifact } from "../lib/open-chat-artifact";
import type { ChatArtifact } from "../model/artifact";
import { closeArtifactsPanelAtom } from "../state/artifacts-panel.atom";

export function ArtifactRow({ artifact }: { artifact: ChatArtifact }) {
	const openArtifactPanel = useSetAtom(openArtifactPanelAtom);
	const closeArtifactsPanel = useSetAtom(closeArtifactsPanelAtom);
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const canDownload = Number.isFinite(workspaceId) && workspaceId > 0;

	const handleOpen = () => {
		void openChatArtifact(artifact, "in-chat", {
			closeArtifactsPanel,
			isDesktop,
			openArtifactPanel,
		});
	};

	return (
		<div className="group relative flex min-h-20 w-full items-center gap-3 rounded-xl border bg-muted/30 px-3 py-3 text-left transition-colors hover:bg-accent hover:text-accent-foreground">
			<button
				type="button"
				onClick={handleOpen}
				className="absolute inset-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				<span className="sr-only">Open {artifact.title}</span>
			</button>
			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
				<ArtifactFormatIcon format={artifact.format} className="size-4" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{artifact.title}</span>
				<ArtifactFormatLabel
					format={artifact.format}
					className="mt-0.5 text-xs text-muted-foreground"
				/>
			</span>
			{canDownload ? (
				<ArtifactDownloadButton
					path={artifactDownloadPath(workspaceId, artifact.artifactId)}
					filename={`${artifact.title}.${artifact.format}`}
					className="relative z-10 size-9 shrink-0 text-muted-foreground hover:text-foreground"
				/>
			) : null}
		</div>
	);
}
