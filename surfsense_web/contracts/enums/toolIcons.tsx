import {
	BookOpen,
	Brain,
	Database,
	FileText,
	Globe,
	ImageIcon,
	Link2,
	type LucideIcon,
	Podcast,
	ScanLine,
	Sparkles,
	Wrench,
} from "lucide-react";

const TOOL_ICONS: Record<string, LucideIcon> = {
	search_knowledge_base: Database,
	generate_podcast: Podcast,
	generate_report: FileText,
	link_preview: Link2,
	display_image: ImageIcon,
	generate_image: Sparkles,
	scrape_webpage: ScanLine,
	web_search: Globe,
	search_surfsense_docs: BookOpen,
	save_memory: Brain,
	recall_memory: Brain,
};

export function getToolIcon(name: string): LucideIcon {
	return TOOL_ICONS[name] ?? Wrench;
}

export const CONNECTOR_TOOL_ICON_PATHS: Record<string, { src: string; alt: string }> = {
	gmail: { src: "/connectors/google-gmail.svg", alt: "Gmail" },
	google_calendar: { src: "/connectors/google-calendar.svg", alt: "Google Calendar" },
	google_drive: { src: "/connectors/google-drive.svg", alt: "Google Drive" },
	notion: { src: "/connectors/notion.svg", alt: "Notion" },
	linear: { src: "/connectors/linear.svg", alt: "Linear" },
};
