import { useAtomValue, useSetAtom } from "jotai";
import { AudioLines, FileText, ImageIcon, Presentation } from "lucide-react";
import type { ComponentType } from "react";
import { openArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { ArtifactDownloadButton } from "@/features/artifacts/artifact-download-button";
import { artifactDownloadPath } from "@/features/artifacts/download-file";
import { useMediaQuery } from "@/hooks/use-media-query";
import { scrollToArtifact } from "../lib/scroll-to-artifact";
import type { ArtifactKind, ChatArtifact } from "../model/artifact";
import { closeArtifactsPanelAtom } from "../state/artifacts-panel.atom";

const KIND_META: Record<
	ArtifactKind,
	{ icon: ComponentType<{ className?: string }>; label: string }
> = {
	file: { icon: FileText, label: "Document" },
	podcast: { icon: AudioLines, label: "Podcast" },
	video: { icon: Presentation, label: "Presentation" },
	image: { icon: ImageIcon, label: "Image" },
};

const FORMAT_LABELS: Record<string, string> = {
	xlsx: "Spreadsheet · XLSX",
	csv: "Table · CSV",
	pdf: "Document · PDF",
	docx: "Document · DOCX",
	pptx: "Presentation · PPTX",
	markdown: "Document · Markdown",
	md: "Document · Markdown",
	py: "Code · PY",
	js: "Code · JS",
	ts: "Code · TS",
};

function subtitle(artifact: ChatArtifact): string {
	if (artifact.kind !== "file") return KIND_META[artifact.kind].label;
	return FORMAT_LABELS[artifact.format.toLowerCase()] ?? `File · ${artifact.format.toUpperCase()}`;
}

export function ArtifactRow({ artifact }: { artifact: ChatArtifact }) {
	const openArtifactPanel = useSetAtom(openArtifactPanelAtom);
	const closeArtifactsPanel = useSetAtom(closeArtifactsPanelAtom);
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const meta = KIND_META[artifact.kind];
	const Icon = meta.icon;
	const canDownload = Number.isFinite(workspaceId) && workspaceId > 0;

	const handleOpen = () => {
		if (artifact.kind === "file") {
			if (!isDesktop) closeArtifactsPanel();
			openArtifactPanel({ artifactId: artifact.artifactId });
			scrollToArtifact(artifact.toolCallId);
			return;
		}

		// Inline media jumps to its card. Mobile dismisses the drawer first since
		// it covers the chat.
		if (!isDesktop) closeArtifactsPanel();
		scrollToArtifact(artifact.toolCallId);
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
				<Icon className="size-4" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{artifact.title}</span>
				<span className="mt-0.5 block truncate text-xs text-muted-foreground">
					{subtitle(artifact)}
				</span>
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
