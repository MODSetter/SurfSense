"use client";

import { getAnnotationData, type Message } from "@llamaindex/chat-ui";
import {
	IconBrandDiscord,
	IconBrandGithub,
	IconBrandNotion,
	IconBrandSlack,
	IconBrandYoutube,
} from "@tabler/icons-react";
import {
	BookOpen,
	Calendar,
	CheckSquare,
	ExternalLink,
	FileText,
	Globe,
	Link2,
	Mail,
	Puzzle,
} from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface Source {
	id: string;
	title: string;
	description: string;
	url: string;
}

interface SourceGroup {
	id: number;
	name: string;
	type: string;
	sources: Source[];
}

// New interfaces for the updated data format
interface NodeMetadata {
	title: string;
	source_type: string;
	group_name: string;
}

interface SourceNode {
	id: string;
	text: string;
	url: string;
	metadata: NodeMetadata;
}

function getSourceIcon(type: string) {
	switch (type) {
		// GitHub
		case "USER_SELECTED_GITHUB_CONNECTOR":
		case "GITHUB_CONNECTOR":
			return <IconBrandGithub className="h-4 w-4" />;

		// Notion
		case "USER_SELECTED_NOTION_CONNECTOR":
		case "NOTION_CONNECTOR":
			return <IconBrandNotion className="h-4 w-4" />;

		// Slack
		case "USER_SELECTED_SLACK_CONNECTOR":
		case "SLACK_CONNECTOR":
			return <IconBrandSlack className="h-4 w-4" />;

		// Discord
		case "USER_SELECTED_DISCORD_CONNECTOR":
		case "DISCORD_CONNECTOR":
			return <IconBrandDiscord className="h-4 w-4" />;

		// Google Calendar
		case "USER_SELECTED_GOOGLE_CALENDAR_CONNECTOR":
		case "GOOGLE_CALENDAR_CONNECTOR":
			return <Calendar className="h-4 w-4" />;

		// Google Gmail
		case "USER_SELECTED_GOOGLE_GMAIL_CONNECTOR":
		case "GOOGLE_GMAIL_CONNECTOR":
			return <Mail className="h-4 w-4" />;

		// YouTube
		case "USER_SELECTED_YOUTUBE_VIDEO":
		case "YOUTUBE_VIDEO":
			return <IconBrandYoutube className="h-4 w-4" />;

		// Linear
		case "USER_SELECTED_LINEAR_CONNECTOR":
		case "LINEAR_CONNECTOR":
			return <CheckSquare className="h-4 w-4" />;

		// Jira
		case "USER_SELECTED_JIRA_CONNECTOR":
		case "JIRA_CONNECTOR":
			return <CheckSquare className="h-4 w-4" />;

		// Confluence
		case "USER_SELECTED_CONFLUENCE_CONNECTOR":
		case "CONFLUENCE_CONNECTOR":
			return <BookOpen className="h-4 w-4" />;

		// ClickUp
		case "USER_SELECTED_CLICKUP_CONNECTOR":
		case "CLICKUP_CONNECTOR":
			return <CheckSquare className="h-4 w-4" />;

		// Files
		case "USER_SELECTED_FILE":
		case "FILE":
			return <FileText className="h-4 w-4" />;

		// Extension
		case "USER_SELECTED_EXTENSION":
		case "EXTENSION":
			return <Puzzle className="h-4 w-4" />;

		// Crawled URL
		case "USER_SELECTED_CRAWLED_URL":
		case "CRAWLED_URL":
			return <Link2 className="h-4 w-4" />;

		// Default for any other source type
		default:
			return <Globe className="h-4 w-4" />;
	}
}

function SourceCard({ source }: { source: Source }) {
	const hasUrl = source.url && source.url.trim() !== "";

	// Clean up the description for better display
	const cleanDescription = source.description
		.replace(/## Metadata\n\n/g, "")
		.replace(/\n+/g, " ")
		.trim();

	return (
		<Card className="border-muted hover:border-muted-foreground/20 transition-colors">
			<CardHeader className="pb-3 pt-3">
				<div className="flex items-start justify-between gap-2">
					<CardTitle className="text-sm font-medium leading-tight line-clamp-2">
						{source.title}
					</CardTitle>
					{hasUrl && (
						<Button
							variant="ghost"
							size="sm"
							className="h-7 w-7 p-0 flex-shrink-0 hover:bg-muted"
							onClick={() => window.open(source.url, "_blank")}
						>
							<ExternalLink className="h-3.5 w-3.5" />
						</Button>
					)}
				</div>
			</CardHeader>
			<CardContent className="pt-0 pb-3">
				<CardDescription className="text-xs line-clamp-3 leading-relaxed text-muted-foreground">
					{cleanDescription}
				</CardDescription>
			</CardContent>
		</Card>
	);
}

export default function ChatSourcesDisplay({ message }: { message: Message }) {
	const [open, setOpen] = useState(false);
	const annotations = getAnnotationData(message, "sources");

	// Transform the new data format to the expected SourceGroup format
	const sourceGroups: SourceGroup[] = [];

	if (Array.isArray(annotations) && annotations.length > 0) {
		// Extract all nodes from the response
		const allNodes: SourceNode[] = [];

		annotations.forEach((item) => {
			if (item && typeof item === "object" && "nodes" in item && Array.isArray(item.nodes)) {
				allNodes.push(...item.nodes);
			}
		});

		// Group nodes by source_type
		const groupedByType = allNodes.reduce(
			(acc, node) => {
				const sourceType = node.metadata.source_type;
				if (!acc[sourceType]) {
					acc[sourceType] = [];
				}
				acc[sourceType].push(node);
				return acc;
			},
			{} as Record<string, SourceNode[]>
		);

		// Convert grouped nodes to SourceGroup format
		Object.entries(groupedByType).forEach(([sourceType, nodes], index) => {
			if (nodes.length > 0) {
				const firstNode = nodes[0];
				sourceGroups.push({
					id: index + 100, // Generate unique ID
					name: firstNode.metadata.group_name,
					type: sourceType,
					sources: nodes.map((node) => ({
						id: node.id,
						title: node.metadata.title,
						description: node.text,
						url: node.url || "",
					})),
				});
			}
		});
	}

	if (sourceGroups.length === 0) {
		return null;
	}

	const totalSources = sourceGroups.reduce((acc, group) => acc + group.sources.length, 0);

	return (
		<Sheet open={open} onOpenChange={setOpen}>
			<SheetTrigger asChild>
				<Button variant="outline" size="sm" className="w-fit">
					<FileText className="h-4 w-4 mr-2" />
					View Sources ({totalSources})
				</Button>
			</SheetTrigger>
			<SheetContent className="w-[400px] sm:w-[540px] md:w-[640px] lg:w-[720px] xl:w-[800px] sm:max-w-[540px] md:max-w-[640px] lg:max-w-[720px] xl:max-w-[800px] flex flex-col p-0 overflow-hidden">
				<SheetHeader className="px-6 py-4 border-b flex-shrink-0">
					<div className="flex items-center justify-between">
						<SheetTitle className="text-lg font-semibold">Sources</SheetTitle>
						<Badge variant="outline" className="font-normal">
							{totalSources} {totalSources === 1 ? "source" : "sources"}
						</Badge>
					</div>
				</SheetHeader>
				<Tabs defaultValue={sourceGroups[0]?.type} className="flex-1 flex flex-col min-h-0">
					<div className="flex-shrink-0 w-full overflow-x-auto px-6 pt-4 scrollbar-none">
						<TabsList className="flex w-max min-w-full bg-muted/50">
							{sourceGroups.map((group) => (
								<TabsTrigger
									key={group.type}
									value={group.type}
									className="flex items-center gap-2 whitespace-nowrap px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm"
								>
									{getSourceIcon(group.type)}
									<span className="truncate max-w-[120px] md:max-w-[180px] lg:max-w-none">
										{group.name}
									</span>
									<Badge variant="secondary" className="ml-1.5 h-5 text-xs flex-shrink-0">
										{group.sources.length}
									</Badge>
								</TabsTrigger>
							))}
						</TabsList>
					</div>
					{sourceGroups.map((group) => (
						<TabsContent
							key={group.type}
							value={group.type}
							className="flex-1 min-h-0 mt-0 px-6 pb-6 data-[state=active]:flex data-[state=active]:flex-col"
						>
							<div className="h-full overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
								<div className="grid gap-3 pt-4 grid-cols-1 lg:grid-cols-2">
									{group.sources.map((source) => (
										<SourceCard key={source.id} source={source} />
									))}
								</div>
							</div>
						</TabsContent>
					))}
				</Tabs>
			</SheetContent>
		</Sheet>
	);
}
