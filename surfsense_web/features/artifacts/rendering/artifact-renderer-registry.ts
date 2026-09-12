"use client";

import dynamic from "next/dynamic";
import { createElement } from "react";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Spinner } from "@/components/ui/spinner";
import { isArtifactDownloadable } from "@/features/artifacts/lib/artifact-format-catalog";
import type { ArtifactRendererResolution } from "@/features/artifacts/lib/artifact-resolution";
import { selectPrimaryArtifactFile } from "@/features/artifacts/lib/artifact-selectors";
import type {
	ArtifactRenderer,
	ArtifactRendererActionsProps,
	ArtifactRendererProps,
} from "@/features/artifacts/model/renderer";
import { cannotPreviewMessage } from "@/features/file-viewers/file-format";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";
import { createMimeArtifactRenderer } from "./mime-artifact-renderer";
import { MIME_VIEWERS } from "./mime-viewer-registry";

function RendererLoading() {
	return createElement(
		"div",
		{ className: "flex h-full items-center justify-center", "aria-busy": true },
		createElement(Spinner, { size: "lg" })
	);
}

const MindMapViewer = dynamic<ArtifactRendererProps>(
	() => import("./formats/mindmap/mindmap-viewer"),
	{ ssr: false, loading: RendererLoading }
);
const FlashcardsViewer = dynamic<ArtifactRendererProps>(
	() => import("./formats/flashcards/flashcards-viewer"),
	{ ssr: false, loading: RendererLoading }
);
const FlashcardActions = dynamic<ArtifactRendererActionsProps>(
	() => import("./formats/flashcards/flashcard-actions"),
	{ ssr: false }
);
const QuizViewer = dynamic<ArtifactRendererProps>(() => import("./formats/quiz/quiz-viewer"), {
	ssr: false,
	loading: RendererLoading,
});

export const SEMANTIC_RENDERERS: Readonly<Record<string, ArtifactRenderer>> = {
	mindmap: { Viewer: MindMapViewer, downloadable: isArtifactDownloadable("mindmap") },
	flashcards: {
		Viewer: FlashcardsViewer,
		Actions: FlashcardActions,
		downloadable: isArtifactDownloadable("flashcards"),
	},
	quiz: { Viewer: QuizViewer, downloadable: isArtifactDownloadable("quiz") },
};

export const SEMANTIC_RENDERER_FORMATS = new Set(Object.keys(SEMANTIC_RENDERERS));

const mimeRenderers: Record<string, ArtifactRenderer> = {};
for (const [mimeType, Viewer] of Object.entries(MIME_VIEWERS)) {
	if (Viewer) mimeRenderers[mimeType] = createMimeArtifactRenderer(Viewer);
}
export const MIME_RENDERERS: Readonly<Record<string, ArtifactRenderer>> = mimeRenderers;

const MarkdownArtifactViewer = ({ manifest }: ArtifactRendererProps) =>
	createElement(
		"div",
		{ className: "h-full overflow-y-auto px-5 py-4" },
		createElement(MarkdownViewer, {
			content: manifest.markdown_representation,
			className: "mx-auto max-w-3xl",
		})
	);

const UnviewableArtifact = ({ manifest }: ArtifactRendererProps) => {
	const primary = selectPrimaryArtifactFile(manifest);
	return createElement(UnviewableFile, {
		message: primary
			? cannotPreviewMessage(primary.filename)
			: "This artifact has no primary file.",
	});
};

const MARKDOWN_RENDERER: ArtifactRenderer = {
	Viewer: MarkdownArtifactViewer,
	downloadable: true,
};
const UNVIEWABLE_RENDERER: ArtifactRenderer = {
	Viewer: UnviewableArtifact,
	downloadable: true,
};

export function getArtifactRenderer(resolution: ArtifactRendererResolution): ArtifactRenderer {
	if (resolution.kind === "semantic") return SEMANTIC_RENDERERS[resolution.key];
	if (resolution.kind === "mime") return MIME_RENDERERS[resolution.key];
	if (resolution.kind === "markdown") return MARKDOWN_RENDERER;
	return UNVIEWABLE_RENDERER;
}
