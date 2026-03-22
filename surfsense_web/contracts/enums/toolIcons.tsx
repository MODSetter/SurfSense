import {
	BookOpen,
	Brain,
	Database,
	FileText,
	Film,
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
	generate_video_presentation: Film,
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
