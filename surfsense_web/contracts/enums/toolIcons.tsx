import {
	BookOpen,
	Brain,
	FileText,
	Film,
	Globe,
	ImageIcon,
	type LucideIcon,
	Podcast,
	ScanLine,
	Wrench,
} from "lucide-react";

const TOOL_ICONS: Record<string, LucideIcon> = {
	generate_podcast: Podcast,
	generate_video_presentation: Film,
	generate_report: FileText,
	generate_image: ImageIcon,
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
	onedrive: { src: "/connectors/onedrive.svg", alt: "OneDrive" },
	notion: { src: "/connectors/notion.svg", alt: "Notion" },
	linear: { src: "/connectors/linear.svg", alt: "Linear" },
	jira: { src: "/connectors/jira.svg", alt: "Jira" },
	confluence: { src: "/connectors/confluence.svg", alt: "Confluence" },
};

export const CONNECTOR_ICON_TO_TYPES: Record<string, string[]> = {
	gmail: ["GOOGLE_GMAIL_CONNECTOR", "COMPOSIO_GMAIL_CONNECTOR"],
	google_calendar: ["GOOGLE_CALENDAR_CONNECTOR", "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"],
	google_drive: ["GOOGLE_DRIVE_CONNECTOR", "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"],
	onedrive: ["ONEDRIVE_CONNECTOR"],
	notion: ["NOTION_CONNECTOR"],
	linear: ["LINEAR_CONNECTOR"],
	jira: ["JIRA_CONNECTOR"],
	confluence: ["CONFLUENCE_CONNECTOR"],
};
