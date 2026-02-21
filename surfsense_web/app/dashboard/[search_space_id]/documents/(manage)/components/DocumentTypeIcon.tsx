"use client";

import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";

export function getDocumentTypeIcon(type: string, className?: string): React.ReactNode {
	return getConnectorIcon(type, className);
}

export function getDocumentTypeLabel(type: string): string {
	const labelMap: Record<string, string> = {
		EXTENSION: "Extension",
		CRAWLED_URL: "Web Page",
		FILE: "File",
		SLACK_CONNECTOR: "Slack",
		TEAMS_CONNECTOR: "Microsoft Teams",
		NOTION_CONNECTOR: "Notion",
		YOUTUBE_VIDEO: "YouTube Video",
		GITHUB_CONNECTOR: "GitHub",
		LINEAR_CONNECTOR: "Linear",
		DISCORD_CONNECTOR: "Discord",
		JIRA_CONNECTOR: "Jira",
		CONFLUENCE_CONNECTOR: "Confluence",
		CLICKUP_CONNECTOR: "ClickUp",
		GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
		GOOGLE_GMAIL_CONNECTOR: "Gmail",
		GOOGLE_DRIVE_FILE: "Google Drive",
		AIRTABLE_CONNECTOR: "Airtable",
		LUMA_CONNECTOR: "Luma",
		ELASTICSEARCH_CONNECTOR: "Elasticsearch",
		BOOKSTACK_CONNECTOR: "BookStack",
		CIRCLEBACK: "Circleback",
		OBSIDIAN_CONNECTOR: "Obsidian",
		SURFSENSE_DOCS: "SurfSense Docs",
		NOTE: "Note",
		COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Composio Google Drive",
		COMPOSIO_GMAIL_CONNECTOR: "Composio Gmail",
		COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Composio Google Calendar",
	};
	return (
		labelMap[type] ||
		type
			.split("_")
			.map((word) => word.charAt(0) + word.slice(1).toLowerCase())
			.join(" ")
	);
}

export function DocumentTypeChip({ type, className }: { type: string; className?: string }) {
	const icon = getDocumentTypeIcon(type, "h-4 w-4");
	const fullLabel = getDocumentTypeLabel(type);
	const textRef = useRef<HTMLSpanElement>(null);
	const [isTruncated, setIsTruncated] = useState(false);

	useEffect(() => {
		const checkTruncation = () => {
			if (textRef.current) {
				setIsTruncated(textRef.current.scrollWidth > textRef.current.clientWidth);
			}
		};
		checkTruncation();
		window.addEventListener("resize", checkTruncation);
		return () => window.removeEventListener("resize", checkTruncation);
	}, []);

	const chip = (
		<span
			className={`inline-flex items-center gap-1.5 rounded-full bg-accent/80 px-2.5 py-1 text-xs font-medium text-accent-foreground shadow-sm max-w-full overflow-hidden ${className ?? ""}`}
		>
			<span className="flex-shrink-0">{icon}</span>
			<span ref={textRef} className="truncate min-w-0">
				{fullLabel}
			</span>
		</span>
	);

	if (isTruncated) {
		return (
			<Tooltip>
				<TooltipTrigger asChild>{chip}</TooltipTrigger>
				<TooltipContent side="top" className="max-w-xs">
					<p>{fullLabel}</p>
				</TooltipContent>
			</Tooltip>
		);
	}

	return chip;
}
