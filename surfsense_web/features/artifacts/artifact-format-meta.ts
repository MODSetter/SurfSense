import type { LucideIcon } from "lucide-react";
import {
	AudioLines,
	Contact,
	FileCode,
	FileSpreadsheet,
	FileText,
	ImageIcon,
	Presentation,
	Shapes,
} from "lucide-react";

export type ArtifactGroupKey =
	| "files"
	| "reports"
	| "resumes"
	| "podcasts"
	| "presentations"
	| "images";

export type ArtifactViewingMode = "viewer" | "inline-media" | "legacy-report";

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
	"reports",
	"resumes",
	"podcasts",
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
	// Presentation-only key for UI that represents the whole artifact collection.
	artifact: { ...FILE_META, icon: Shapes, label: "Artifact" },
	file: { ...FILE_META, label: "Artifact" },
	markdown: { ...FILE_META, label: "Document", detailLabel: "Markdown" },
	md: { ...FILE_META, label: "Document", detailLabel: "Markdown" },
	pdf: { ...FILE_META, label: "Document", detailLabel: "PDF" },
	docx: { ...FILE_META, label: "Document", detailLabel: "DOCX" },
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
		icon: Presentation,
		label: "Presentation",
		groupKey: "presentations",
		groupLabel: "Presentations",
		viewingMode: "inline-media",
	},
	image: {
		icon: ImageIcon,
		label: "Image",
		groupKey: "images",
		groupLabel: "Images",
		viewingMode: "inline-media",
	},
	// Compatibility-only formats until legacy reports are removed in phase 6.
	report: {
		icon: FileText,
		label: "Report",
		groupKey: "reports",
		groupLabel: "Reports",
		viewingMode: "legacy-report",
	},
	resume: {
		icon: Contact,
		label: "Resume",
		groupKey: "resumes",
		groupLabel: "Resumes",
		viewingMode: "legacy-report",
	},
};

export function normalizeArtifactFormat(format: string | null | undefined): string {
	return format?.trim().toLowerCase() || "file";
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
