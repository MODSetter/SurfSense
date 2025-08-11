"use client";

import {
	IconBook,
	IconBrandDiscord,
	IconBrandGithub,
	IconBrandNotion,
	IconBrandSlack,
	IconBrandYoutube,
	IconCalendar,
	IconChecklist,
	IconLayoutKanban,
	IconTicket,
} from "@tabler/icons-react";
import { File, Globe, Webhook } from "lucide-react";
import type React from "react";

type IconComponent = React.ComponentType<{ size?: number; className?: string }>;

const documentTypeIcons: Record<string, IconComponent> = {
	EXTENSION: Webhook,
	CRAWLED_URL: Globe,
	SLACK_CONNECTOR: IconBrandSlack,
	NOTION_CONNECTOR: IconBrandNotion,
	FILE: File,
	YOUTUBE_VIDEO: IconBrandYoutube,
	GITHUB_CONNECTOR: IconBrandGithub,
	LINEAR_CONNECTOR: IconLayoutKanban,
	JIRA_CONNECTOR: IconTicket,
	DISCORD_CONNECTOR: IconBrandDiscord,
	CONFLUENCE_CONNECTOR: IconBook,
	CLICKUP_CONNECTOR: IconChecklist,
	GOOGLE_CALENDAR_CONNECTOR: IconCalendar,
};

export function getDocumentTypeIcon(type: string): IconComponent {
	return documentTypeIcons[type] ?? File;
}

export function getDocumentTypeLabel(type: string): string {
	return type
		.split("_")
		.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
		.join(" ");
}

export function DocumentTypeChip({ type, className }: { type: string; className?: string }) {
	const Icon = getDocumentTypeIcon(type);
	return (
		<span
			className={
				"inline-flex items-center gap-1.5 rounded-full border border-border bg-primary/5 px-2 py-1 text-xs font-medium " +
				(className ?? "")
			}
		>
			<Icon size={14} className="text-primary" />
			{getDocumentTypeLabel(type)}
		</span>
	);
}
