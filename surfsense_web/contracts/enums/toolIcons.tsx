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

/**
 * Friendly display names for tools shown in the chat UI.
 *
 * Most users aren't engineers; they shouldn't see raw unix-style
 * identifiers like ``rm`` / ``rmdir`` / ``ls`` / ``grep`` / ``glob`` or
 * snake_cased function names. The map below renders each tool with
 * plain English wording (verb + object) so non-technical users
 * understand what the agent is doing at a glance.
 *
 * Unmapped tool names fall back to a snake_case-to-Title-Case
 * conversion via :func:`getToolDisplayName`.
 */
const TOOL_DISPLAY_NAMES: Record<string, string> = {
	// Filesystem / knowledge base
	read_file: "Read file",
	write_file: "Write file",
	edit_file: "Edit file",
	move_file: "Move file",
	rm: "Delete file",
	rmdir: "Delete folder",
	mkdir: "Create folder",
	ls: "List files",
	glob: "Find files",
	grep: "Search in files",
	write_todos: "Plan tasks",
	save_document: "Save document",
	// Generators
	generate_podcast: "Generate podcast",
	generate_video_presentation: "Generate video presentation",
	generate_report: "Generate report",
	generate_resume: "Generate resume",
	generate_image: "Generate image",
	display_image: "Show image",
	// Web / search
	scrape_webpage: "Read webpage",
	web_search: "Search the web",
	search_surfsense_docs: "Search knowledge base",
	// Memory
	update_memory: "Update memory",
	// Calendar
	search_calendar_events: "Search calendar",
	create_calendar_event: "Create event",
	update_calendar_event: "Update event",
	delete_calendar_event: "Delete event",
	// Gmail
	search_gmail: "Search Gmail",
	read_gmail_email: "Read email",
	create_gmail_draft: "Draft email",
	update_gmail_draft: "Update draft",
	send_gmail_email: "Send email",
	trash_gmail_email: "Move email to trash",
	// Notion
	create_notion_page: "Create Notion page",
	update_notion_page: "Update Notion page",
	delete_notion_page: "Delete Notion page",
	// Confluence
	create_confluence_page: "Create Confluence page",
	update_confluence_page: "Update Confluence page",
	delete_confluence_page: "Delete Confluence page",
	// Linear
	create_linear_issue: "Create Linear issue",
	update_linear_issue: "Update Linear issue",
	delete_linear_issue: "Delete Linear issue",
	// Jira
	create_jira_issue: "Create Jira issue",
	update_jira_issue: "Update Jira issue",
	delete_jira_issue: "Delete Jira issue",
	// Drive-like file connectors
	create_google_drive_file: "Create Google Drive file",
	delete_google_drive_file: "Delete Google Drive file",
	create_dropbox_file: "Create Dropbox file",
	delete_dropbox_file: "Delete Dropbox file",
	create_onedrive_file: "Create OneDrive file",
	delete_onedrive_file: "Delete OneDrive file",
	// Discord
	list_discord_channels: "List Discord channels",
	read_discord_messages: "Read Discord messages",
	send_discord_message: "Send Discord message",
	// Teams
	list_teams_channels: "List Teams channels",
	read_teams_messages: "Read Teams messages",
	send_teams_message: "Send Teams message",
	// Luma
	list_luma_events: "List Luma events",
	read_luma_event: "Read Luma event",
	create_luma_event: "Create Luma event",
	// Misc
	get_connected_accounts: "Check connected accounts",
	execute: "Run command",
	execute_code: "Run code",
};

/**
 * Format a tool's canonical (snake_case) name for display in the chat UI.
 *
 * Looks up :data:`TOOL_DISPLAY_NAMES` first; falls back to a
 * snake_case-to-Title-Case rewrite for tools that don't have a curated
 * label (e.g. dynamically registered MCP tools).
 */
export function getToolDisplayName(name: string): string {
	const friendly = TOOL_DISPLAY_NAMES[name];
	if (friendly) return friendly;
	return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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
