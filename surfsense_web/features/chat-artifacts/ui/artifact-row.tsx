import { useSetAtom } from "jotai";
import { AudioLines, Contact, FileText, ImageIcon, Presentation } from "lucide-react";
import type { ComponentType } from "react";
import { openReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { Button } from "@/components/ui/button";
import { scrollToArtifact } from "../lib/scroll-to-artifact";
import type { ArtifactKind, ChatArtifact } from "../model/artifact";

const KIND_META: Record<
	ArtifactKind,
	{ icon: ComponentType<{ className?: string }>; label: string }
> = {
	report: { icon: FileText, label: "Report" },
	resume: { icon: Contact, label: "Resume" },
	podcast: { icon: AudioLines, label: "Podcast" },
	video: { icon: Presentation, label: "Presentation" },
	image: { icon: ImageIcon, label: "Image" },
};

export function ArtifactRow({ artifact }: { artifact: ChatArtifact }) {
	const openReportPanel = useSetAtom(openReportPanelAtom);
	const meta = KIND_META[artifact.kind];
	const Icon = meta.icon;
	const isReportLike = artifact.kind === "report" || artifact.kind === "resume";

	const handleOpen = () => {
		scrollToArtifact(artifact.toolCallId);
		// Reports and resumes get the richer side-panel viewer in addition to the jump.
		if (isReportLike && artifact.entityId != null) {
			openReportPanel({
				reportId: artifact.entityId,
				title: artifact.title,
				contentType: artifact.contentType,
			});
		}
	};

	return (
		<Button
			type="button"
			variant="ghost"
			onClick={handleOpen}
			className="h-auto w-full justify-start gap-3 rounded-lg px-3 py-2.5 text-left font-normal hover:bg-accent hover:text-accent-foreground"
		>
			<span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted/60 text-muted-foreground">
				<Icon className="size-4" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{artifact.title}</span>
				<span className="block truncate text-xs text-muted-foreground">
					{artifact.status === "running" ? "Generating…" : meta.label}
				</span>
			</span>
		</Button>
	);
}
