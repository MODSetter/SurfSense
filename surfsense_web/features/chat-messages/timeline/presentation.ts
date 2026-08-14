import {
	BadgeCheck,
	Brain,
	Calendar,
	ExternalLink,
	FileInput,
	FileOutput,
	FilePenLine,
	FilePlus,
	Files,
	FileText,
	FileX,
	Film,
	FolderOpen,
	FolderPlus,
	FolderSearch,
	FolderTree,
	FolderX,
	ImageIcon,
	LibraryBig,
	ListTodo,
	type LucideIcon,
	Mic2,
	Route,
	ScanText,
	Search,
	SearchCode,
	SquareCode,
	Terminal,
	Workflow,
	Wrench,
} from "lucide-react";
import { CONNECTOR_TOOL_ICON_PATHS } from "@/contracts/enums/toolIcons";
import type {
	ActivityCategory,
	ActivityIntegration,
	ActivityVisibility,
	ItemStatus,
	ToolCallItem,
} from "./types";

export interface ToolPresentation {
	icon: LucideIcon;
	active: string;
	completed: string;
	failed: string;
	cancelled: string;
	visibility: ActivityVisibility;
	category: Exclude<ActivityCategory, "reasoning">;
}

const p = (
	icon: LucideIcon,
	active: string,
	completed: string,
	category: ToolPresentation["category"],
	visibility: ActivityVisibility = "show"
): ToolPresentation => ({
	icon,
	active,
	completed,
	failed: `Couldn’t ${active.charAt(0).toLowerCase()}${active.slice(1)}`,
	cancelled: `${active.replace(/ing\b/, "").trim()} stopped`,
	visibility,
	category,
});

const TOOL_PRESENTATIONS: Record<string, ToolPresentation> = {
	read_file: p(FileText, "Reading file", "Read file", "file"),
	write_file: p(FilePlus, "Creating file", "Created file", "file"),
	edit_file: p(FilePenLine, "Editing file", "Edited file", "file"),
	move_file: p(Files, "Moving file", "Moved file", "file"),
	rm: p(FileX, "Deleting file", "Deleted file", "file"),
	mkdir: p(FolderPlus, "Creating folder", "Created folder", "file"),
	rmdir: p(FolderX, "Deleting folder", "Deleted folder", "file"),
	ls: p(FolderOpen, "Reviewing folder", "Reviewed folder", "file"),
	list_tree: p(FolderTree, "Reviewing file tree", "Reviewed file tree", "file"),
	glob: p(FolderSearch, "Finding files", "Found files", "file"),
	grep: p(SearchCode, "Searching project", "Searched project", "file"),
	execute: p(Terminal, "Running command", "Ran command", "action"),
	execute_code: p(SquareCode, "Running code", "Ran code", "action"),
	write_todos: p(ListTodo, "Planning work", "Planned work", "action", "aggregate"),
	load_artifact_source: p(
		FileInput,
		"Opening the artifact",
		"Opened the artifact",
		"artifact",
		"aggregate"
	),
	read_sandbox_file: p(
		FileText,
		"Reviewing the artifact",
		"Reviewed the artifact",
		"artifact",
		"aggregate"
	),
	verify_artifact: p(BadgeCheck, "Checking the artifact", "Checked the artifact", "artifact"),
	save_artifact: p(FileOutput, "Preparing the file", "Presented file", "artifact"),
	save_document: p(FileOutput, "Preparing the document", "Presented document", "artifact"),
	generate_image: p(ImageIcon, "Creating an image", "Created an image", "artifact"),
	display_image: p(ImageIcon, "Preparing the image", "Presented image", "artifact"),
	generate_podcast: p(Mic2, "Creating the podcast", "Created the podcast", "artifact"),
	generate_video_presentation: p(
		Film,
		"Creating the presentation",
		"Created the presentation",
		"artifact"
	),
	search_knowledge_base: p(
		LibraryBig,
		"Searching your sources",
		"Searched your sources",
		"research"
	),
	ask_knowledge_base: p(LibraryBig, "Reviewing your sources", "Reviewed your sources", "research"),
	scrape_webpage: p(ScanText, "Reviewing a webpage", "Reviewed a webpage", "research", "aggregate"),
	"google_search.scrape": p(Search, "Searching the web", "Searched the web", "research"),
	"web.crawl": p(ScanText, "Reviewing the web", "Reviewed the web", "research"),
	"amazon.scrape": p(Search, "Searching Amazon", "Searched Amazon", "research"),
	"walmart.scrape": p(Search, "Searching Walmart", "Searched Walmart", "research"),
	"walmart.reviews": p(
		Search,
		"Reviewing Walmart feedback",
		"Reviewed Walmart feedback",
		"research"
	),
	"google_maps.scrape": p(Search, "Searching Google Maps", "Searched Google Maps", "research"),
	"google_maps.reviews": p(
		Search,
		"Reviewing Google Maps feedback",
		"Reviewed Google Maps feedback",
		"research"
	),
	"indeed.scrape": p(Search, "Searching Indeed", "Searched Indeed", "research"),
	"youtube.scrape": p(Search, "Searching YouTube", "Searched YouTube", "research"),
	"youtube.comments": p(
		Search,
		"Reviewing YouTube comments",
		"Reviewed YouTube comments",
		"research"
	),
	"reddit.scrape": p(Search, "Searching Reddit", "Searched Reddit", "research"),
	"tiktok.scrape": p(Search, "Searching TikTok", "Searched TikTok", "research"),
	"tiktok.comments": p(Search, "Reviewing TikTok comments", "Reviewed TikTok comments", "research"),
	"tiktok.trending": p(Search, "Reviewing TikTok trends", "Reviewed TikTok trends", "research"),
	"tiktok.user_search": p(Search, "Searching TikTok", "Searched TikTok", "research"),
	"instagram.scrape": p(Search, "Searching Instagram", "Searched Instagram", "research"),
	"instagram.details": p(Search, "Reviewing Instagram", "Reviewed Instagram", "research"),
	link_preview: p(ExternalLink, "Reviewing a link", "Reviewed a link", "research", "aggregate"),
	multi_link_preview: p(ExternalLink, "Reviewing links", "Reviewed links", "research", "aggregate"),
	create_calendar_event: p(
		Calendar,
		"Creating calendar event",
		"Created calendar event",
		"connector"
	),
	update_calendar_event: p(
		Calendar,
		"Updating calendar event",
		"Updated calendar event",
		"connector"
	),
	delete_calendar_event: p(
		Calendar,
		"Deleting calendar event",
		"Deleted calendar event",
		"connector"
	),
	search_calendar_events: p(Calendar, "Searching calendar", "Searched calendar", "connector"),
	create_automation: p(Workflow, "Creating automation", "Created automation", "action"),
	update_memory: p(Brain, "Remembering preference", "Remembered preference", "action"),
	task: p(Route, "Working with a specialist", "Worked with a specialist", "action"),
	get_connected_accounts: p(
		Search,
		"Checking connected apps",
		"Checked connected apps",
		"connector",
		"aggregate"
	),
	generate_report: p(FileText, "Creating report", "Created report", "artifact", "hide"),
	generate_resume: p(FileText, "Creating resume", "Created resume", "artifact", "hide"),
	pwd: p(Terminal, "Checking folder", "Checked folder", "file", "hide"),
	cd: p(Terminal, "Changing folder", "Changed folder", "file", "hide"),
	noop: p(Wrench, "Working", "Worked", "action", "hide"),
	invalid_tool: p(Wrench, "Repairing action", "Repaired action", "action", "hide"),
};

const CONNECTOR_TOOL_PREFIXES: Array<[RegExp, string]> = [
	[/gmail/i, "gmail"],
	[/calendar/i, "google_calendar"],
	[/google_drive/i, "google_drive"],
	[/dropbox/i, "dropbox"],
	[/onedrive/i, "onedrive"],
	[/notion/i, "notion"],
	[/linear/i, "linear"],
	[/jira/i, "jira"],
	[/confluence/i, "confluence"],
	[/discord/i, "discord"],
	[/teams/i, "teams"],
	[/luma/i, "luma"],
	[/google_search/i, "google_search"],
	[/google_maps/i, "google_maps"],
	[/amazon/i, "amazon"],
	[/walmart/i, "walmart"],
	[/indeed/i, "indeed"],
	[/youtube/i, "youtube"],
	[/reddit/i, "reddit"],
	[/tiktok/i, "tiktok"],
	[/instagram/i, "instagram"],
	[/^web[._]/i, "web"],
];

const SERVICE_LOGOS: Record<string, { src: string; alt: string }> = {
	google_search: { src: "/connectors/google-search.svg", alt: "Google Search" },
	web: { src: "/connectors/web.svg", alt: "Web" },
	amazon: { src: "/connectors/amazon.svg", alt: "Amazon" },
	walmart: { src: "/connectors/walmart.svg", alt: "Walmart" },
	google_maps: { src: "/connectors/google-maps.svg", alt: "Google Maps" },
	indeed: { src: "/connectors/indeed.svg", alt: "Indeed" },
	youtube: { src: "/connectors/youtube.svg", alt: "YouTube" },
	reddit: { src: "/connectors/reddit.svg", alt: "Reddit" },
	tiktok: { src: "/connectors/tiktok.svg", alt: "TikTok" },
	instagram: { src: "/connectors/instagram.svg", alt: "Instagram" },
};

const BODY_RENDERED_TOOLS = new Set([
	"display_image",
	"generate_image",
	"generate_podcast",
	"generate_video_presentation",
	"save_artifact",
	"save_document",
	"generate_report",
	"generate_resume",
]);

export function inferNativeIntegration(toolName: string): ActivityIntegration | undefined {
	const match = CONNECTOR_TOOL_PREFIXES.find(([pattern]) => pattern.test(toolName));
	return match ? { source: "connector", key: match[1] } : undefined;
}

export function getToolPresentation(toolName: string): ToolPresentation {
	const name = humanizeToolName(toolName);
	return TOOL_PRESENTATIONS[toolName] ?? p(Wrench, `Using ${name}`, `Used ${name}`, "action");
}

export function getConnectorLogo(integration: ActivityIntegration | undefined) {
	if (integration?.key && CONNECTOR_TOOL_ICON_PATHS[integration.key]) {
		return CONNECTOR_TOOL_ICON_PATHS[integration.key];
	}
	if (integration?.key && SERVICE_LOGOS[integration.key]) return SERVICE_LOGOS[integration.key];
	if (integration?.source === "mcp") {
		return { src: "/connectors/modelcontextprotocol.svg", alt: "Connected app" };
	}
	return undefined;
}

export function resolvePresentationTitle(item: ToolCallItem): string {
	const presentation = getToolPresentation(item.toolName);
	if (item.context?.subagentType === "deliverables") {
		const artifact = item.context.artifactType ?? "artifact";
		const completed = item.status === "completed";
		if (item.context.intent === "author")
			return `${completed ? "Created" : "Creating"} the ${artifact}`;
		if (item.context.intent === "verify")
			return `${completed ? "Checked" : "Checking"} the ${artifact}`;
		if (item.context.intent === "inspect")
			return `${completed ? "Reviewed" : "Reviewing"} the ${artifact}`;
		if (item.context.intent === "persist")
			return completed ? "Presented file" : "Preparing the file";
	}
	const detail = item.safeDetail?.filename ?? item.safeDetail?.subject;
	const base =
		item.status === "running" || item.status === "pending"
			? presentation.active
			: item.status === "completed"
				? presentation.completed
				: item.status === "cancelled" || item.status === "interrupted"
					? presentation.cancelled
					: item.status === "awaiting_approval"
						? `Waiting to ${presentation.active.toLowerCase()}`
						: presentation.failed;
	return detail && presentation.visibility === "show" ? `${base} ${detail}` : base;
}

export function getToolVisibility(toolName: string): ActivityVisibility {
	return getToolPresentation(toolName).visibility;
}

export function getToolCategory(toolName: string): ToolPresentation["category"] {
	return getToolPresentation(toolName).category;
}

export function shouldRenderTimelineBody(toolName: string): boolean {
	return !BODY_RENDERED_TOOLS.has(toolName);
}

export function humanizeToolName(name: string): string {
	const text = name.replace(/[._-]+/g, " ").trim();
	return text ? text.replace(/\b\w/g, (character) => character.toUpperCase()) : "Using tool";
}

export function mapTerminalTitle(presentation: ToolPresentation, status: ItemStatus): string {
	if (status === "completed") return presentation.completed;
	if (status === "error") return presentation.failed;
	if (status === "cancelled" || status === "interrupted") return presentation.cancelled;
	return presentation.active;
}
