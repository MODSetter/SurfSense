import {
	BadgeCheck,
	Brain,
	Calendar,
	Clapperboard,
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
	SquareTerminal,
	Terminal,
	Workflow,
	Wrench,
} from "lucide-react";
import { CONNECTOR_TOOL_ICON_PATHS } from "@/contracts/enums/toolIcons";
import type { ActivityData, ActivityStatus } from "@/lib/chat/activity-journal";

export function getActivityPresentation(
	activity: ActivityData,
	threadRunning: boolean
): { status: ActivityStatus; title: string } {
	const status = activity.status === "running" && !threadRunning ? "interrupted" : activity.status;
	return {
		status,
		title: status === "running" && activity.progressTitle ? activity.progressTitle : activity.title,
	};
}

const ACTIVITY_ICONS: Record<string, LucideIcon> = {
	"badge-check": BadgeCheck,
	brain: Brain,
	calendar: Calendar,
	clapperboard: Clapperboard,
	"external-link": ExternalLink,
	file: FileText,
	"file-input": FileInput,
	"file-output": FileOutput,
	"file-pen": FilePenLine,
	"file-plus": FilePlus,
	"file-text": FileText,
	"file-x": FileX,
	files: Files,
	film: Film,
	"folder-open": FolderOpen,
	"folder-plus": FolderPlus,
	"folder-search": FolderSearch,
	"folder-tree": FolderTree,
	"folder-x": FolderX,
	image: ImageIcon,
	library: LibraryBig,
	"list-todo": ListTodo,
	microphone: Mic2,
	route: Route,
	"scan-text": ScanText,
	"search-code": SearchCode,
	search: Search,
	"square-code": SquareCode,
	"square-terminal": SquareTerminal,
	terminal: Terminal,
	tool: Wrench,
	research: Search,
	artifact: FileOutput,
	connector: Workflow,
	action: Wrench,
	workflow: Workflow,
};

export function getActivityIcon(iconKey: string, category: ActivityData["category"]): LucideIcon {
	return ACTIVITY_ICONS[iconKey] ?? ACTIVITY_ICONS[category] ?? Wrench;
}

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

export function getConnectorLogo(integration: ActivityData["integration"]) {
	if (integration?.key && CONNECTOR_TOOL_ICON_PATHS[integration.key]) {
		return CONNECTOR_TOOL_ICON_PATHS[integration.key];
	}
	if (integration?.key && SERVICE_LOGOS[integration.key]) return SERVICE_LOGOS[integration.key];
	if (integration?.source === "mcp") {
		return { src: "/connectors/modelcontextprotocol.svg", alt: "Connected app" };
	}
	return undefined;
}
