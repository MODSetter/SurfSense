import {
	BookOpen,
	Brain,
	Calendar,
	Check,
	FileEdit,
	FilePlus,
	FileText,
	FileUser,
	FileX,
	Film,
	FolderPlus,
	FolderTree,
	FolderX,
	Globe,
	ImageIcon,
	ListTodo,
	type LucideIcon,
	Mail,
	MessagesSquare,
	Move,
	Plus,
	Podcast,
	ScanLine,
	Search,
	Send,
	Trash2,
	Wrench,
} from "lucide-react";

/**
 * Every tool now renders a card via ``ToolFallback``. The icon map is
 * keyed on the canonical backend tool name (registered in
 * ``surfsense_backend/app/agents/new_chat/tools/registry.py``); unknown
 * names fall back to the generic ``Wrench`` icon so the card still
 * communicates "this is a tool call".
 */
const TOOL_ICONS: Record<string, LucideIcon> = {
	// Generators
	generate_podcast: Podcast,
	generate_video_presentation: Film,
	generate_report: FileText,
	generate_resume: FileUser,
	generate_image: ImageIcon,
	display_image: ImageIcon,
	// Web / search
	scrape_webpage: ScanLine,
	web_search: Globe,
	search_surfsense_docs: BookOpen,
	// Memory
	update_memory: Brain,
	// Filesystem (built-in deepagent + middleware)
	read_file: FileText,
	write_file: FilePlus,
	edit_file: FileEdit,
	move_file: Move,
	rm: FileX,
	rmdir: FolderX,
	mkdir: FolderPlus,
	ls: FolderTree,
	write_todos: ListTodo,
	// Calendar
	search_calendar_events: Search,
	create_calendar_event: Calendar,
	update_calendar_event: Calendar,
	delete_calendar_event: Calendar,
	// Gmail
	search_gmail: Search,
	read_gmail_email: Mail,
	create_gmail_draft: Mail,
	update_gmail_draft: FileEdit,
	send_gmail_email: Send,
	trash_gmail_email: Trash2,
	// Notion / Confluence pages
	create_notion_page: FilePlus,
	update_notion_page: FileEdit,
	delete_notion_page: FileX,
	create_confluence_page: FilePlus,
	update_confluence_page: FileEdit,
	delete_confluence_page: FileX,
	// Linear / Jira issues
	create_linear_issue: Plus,
	update_linear_issue: FileEdit,
	delete_linear_issue: Trash2,
	create_jira_issue: Plus,
	update_jira_issue: FileEdit,
	delete_jira_issue: Trash2,
	// Drive-like file connectors
	create_google_drive_file: FilePlus,
	delete_google_drive_file: FileX,
	create_dropbox_file: FilePlus,
	delete_dropbox_file: FileX,
	create_onedrive_file: FilePlus,
	delete_onedrive_file: FileX,
	// Chat connectors
	list_discord_channels: MessagesSquare,
	read_discord_messages: MessagesSquare,
	send_discord_message: Send,
	list_teams_channels: MessagesSquare,
	read_teams_messages: MessagesSquare,
	send_teams_message: Send,
	// Luma
	list_luma_events: Calendar,
	read_luma_event: Calendar,
	create_luma_event: Calendar,
	// Misc
	get_connected_accounts: Check,
	execute: Wrench,
	execute_code: Wrench,
};

export function getToolIcon(name: string): LucideIcon {
	return TOOL_ICONS[name] ?? Wrench;
}

export const CONNECTOR_TOOL_ICON_PATHS: Record<string, { src: string; alt: string }> = {
	gmail: { src: "/connectors/google-gmail.svg", alt: "Gmail" },
	google_calendar: { src: "/connectors/google-calendar.svg", alt: "Google Calendar" },
	google_drive: { src: "/connectors/google-drive.svg", alt: "Google Drive" },
	dropbox: { src: "/connectors/dropbox.svg", alt: "Dropbox" },
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
	dropbox: ["DROPBOX_CONNECTOR"],
	onedrive: ["ONEDRIVE_CONNECTOR"],
	notion: ["NOTION_CONNECTOR"],
	linear: ["LINEAR_CONNECTOR"],
	jira: ["JIRA_CONNECTOR"],
	confluence: ["CONFLUENCE_CONNECTOR"],
};
