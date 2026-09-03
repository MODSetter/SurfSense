import type { LucideIcon } from "lucide-react";
import {
	AudioLines,
	FileCode,
	FileSpreadsheet,
	FileText,
	ImageIcon,
	ListChecks,
	Network,
	PlayingCardsFan,
	Presentation,
	Shapes,
	Video,
} from "lucide-react";

export type ArtifactGroupKey = "files" | "podcasts" | "videos" | "presentations" | "images";
export type ArtifactViewingMode = "viewer" | "inline-media";

export interface ArtifactFormatMeta {
	icon: LucideIcon;
	label: string;
	detailLabel?: string;
	groupKey: ArtifactGroupKey;
	groupLabel: string;
	viewingMode: ArtifactViewingMode;
}

export const ARTIFACT_GROUP_ORDER: readonly ArtifactGroupKey[] = [
	"files",
	"podcasts",
	"videos",
	"presentations",
	"images",
];

const FILE_META = {
	icon: FileText,
	groupKey: "files",
	groupLabel: "Files",
	viewingMode: "viewer",
} as const;

const FORMAT_META: Record<string, ArtifactFormatMeta> = {
	artifact: { ...FILE_META, icon: Shapes, label: "Artifact" },
	file: { ...FILE_META, label: "Artifact" },
	markdown: { ...FILE_META, label: "Document", detailLabel: "Markdown" },
	md: { ...FILE_META, label: "Document", detailLabel: "Markdown" },
	pdf: { ...FILE_META, label: "Document", detailLabel: "PDF" },
	docx: { ...FILE_META, label: "Document", detailLabel: "DOCX" },
	mindmap: { ...FILE_META, icon: Network, label: "Interactive", detailLabel: "Mind map" },
	flashcards: {
		...FILE_META,
		icon: PlayingCardsFan,
		label: "Interactive",
		detailLabel: "Flashcards",
	},
	quiz: {
		...FILE_META,
		icon: ListChecks,
		label: "Interactive",
		detailLabel: "Quiz",
	},
	pptx: {
		icon: Presentation,
		label: "Presentation",
		detailLabel: "PPTX",
		groupKey: "files",
		groupLabel: "Files",
		viewingMode: "viewer",
	},
	xlsx: {
		icon: FileSpreadsheet,
		label: "Spreadsheet",
		detailLabel: "XLSX",
		groupKey: "files",
		groupLabel: "Files",
		viewingMode: "viewer",
	},
	html: {
		icon: FileCode,
		label: "Code",
		detailLabel: "HTML",
		groupKey: "files",
		groupLabel: "Files",
		viewingMode: "viewer",
	},
	csv: {
		icon: FileSpreadsheet,
		label: "Table",
		detailLabel: "CSV",
		groupKey: "files",
		groupLabel: "Files",
		viewingMode: "viewer",
	},
	py: {
		icon: FileCode,
		label: "Code",
		detailLabel: "PY",
		groupKey: "files",
		groupLabel: "Files",
		viewingMode: "viewer",
	},
	js: {
		icon: FileCode,
		label: "Code",
		detailLabel: "JS",
		groupKey: "files",
		groupLabel: "Files",
		viewingMode: "viewer",
	},
	ts: {
		icon: FileCode,
		label: "Code",
		detailLabel: "TS",
		groupKey: "files",
		groupLabel: "Files",
		viewingMode: "viewer",
	},
	podcast: {
		icon: AudioLines,
		label: "Podcast",
		groupKey: "podcasts",
		groupLabel: "Podcasts",
		viewingMode: "inline-media",
	},
	video: {
		icon: Video,
		label: "Video",
		detailLabel: "MP4",
		groupKey: "videos",
		groupLabel: "Videos",
		viewingMode: "inline-media",
	},
	image: {
		icon: ImageIcon,
		label: "Image",
		groupKey: "images",
		groupLabel: "Images",
		viewingMode: "inline-media",
	},
	infographic: {
		icon: ImageIcon,
		label: "Infographic",
		detailLabel: "PNG",
		groupKey: "images",
		groupLabel: "Images",
		viewingMode: "viewer",
	},
};

const NON_DOWNLOADABLE_FORMATS = new Set(["flashcards", "quiz"]);

export function normalizeArtifactFormat(format: string | null | undefined): string {
	return format?.trim().toLowerCase() || "file";
}

export function isArtifactDownloadable(format: string | null | undefined): boolean {
	return !NON_DOWNLOADABLE_FORMATS.has(normalizeArtifactFormat(format));
}

export function getArtifactFormatMeta(format: string | null | undefined): ArtifactFormatMeta {
	const normalized = normalizeArtifactFormat(format);
	return (
		FORMAT_META[normalized] ?? {
			...FILE_META,
			label: "File",
			detailLabel: normalized.toUpperCase(),
		}
	);
}
