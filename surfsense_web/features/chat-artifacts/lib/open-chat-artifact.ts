import { getArtifactFormatMeta } from "@/features/artifacts/lib/artifact-format-catalog";
import type { ChatArtifact } from "../model/artifact";
import { scrollToArtifact } from "./scroll-to-artifact";

type ArtifactOpenSource = "deep-link" | "in-chat";

interface OpenChatArtifactDependencies {
	closeArtifactsPanel: () => void;
	isDesktop: boolean;
	openArtifactPanel: (payload: {
		artifactId: number;
		selectedCardToolCallId?: string | null;
	}) => void;
}

interface ArtifactOpenPlan {
	behavior: ScrollBehavior;
	highlight: boolean;
	openViewer: boolean;
}

type ResolvedChatArtifact = ChatArtifact & { artifactId: number };

export function getArtifactOpenPlan(format: string, source: ArtifactOpenSource): ArtifactOpenPlan {
	const openViewer = getArtifactFormatMeta(format).viewingMode === "viewer";
	return {
		behavior: source === "deep-link" ? "instant" : "smooth",
		highlight: !openViewer,
		openViewer,
	};
}

/**
 * Apply the same artifact-opening policy for sidebar clicks and library links.
 * Backend `Artifact.format` selects the viewer; the source only selects motion.
 */
export function openChatArtifact(
	artifact: ResolvedChatArtifact,
	source: ArtifactOpenSource,
	{ closeArtifactsPanel, isDesktop, openArtifactPanel }: OpenChatArtifactDependencies
): Promise<void> {
	const plan = getArtifactOpenPlan(artifact.format, source);

	if (!isDesktop) closeArtifactsPanel();
	if (plan.openViewer) {
		openArtifactPanel({
			artifactId: artifact.artifactId,
			selectedCardToolCallId: artifact.toolCallId,
		});
	}

	return scrollToArtifact(artifact.toolCallId, {
		behavior: plan.behavior,
		highlight: plan.highlight,
	});
}
