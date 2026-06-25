import { AudioLines, Contact, FileText, ImageIcon, Presentation } from "lucide-react";
import type { ComponentType } from "react";
import type { LibraryArtifactKind } from "../model/artifact";

export const KIND_META: Record<
	LibraryArtifactKind,
	{ icon: ComponentType<{ className?: string }>; label: string; group: string }
> = {
	report: { icon: FileText, label: "Report", group: "Reports" },
	resume: { icon: Contact, label: "Resume", group: "Resumes" },
	podcast: { icon: AudioLines, label: "Podcast", group: "Podcasts" },
	video: { icon: Presentation, label: "Presentation", group: "Presentations" },
	image: { icon: ImageIcon, label: "Image", group: "Images" },
};

export const KIND_ORDER: LibraryArtifactKind[] = ["report", "resume", "podcast", "video", "image"];
