"use client";

import { useState } from "react";
import { getAnnotationData, Message } from "@llamaindex/chat-ui";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, FileText, Globe } from "lucide-react";
import { IconBrandGithub } from "@tabler/icons-react";

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

interface NodesResponse {
	nodes: SourceNode[];
}

function getSourceIcon(type: string) {
	switch (type) {
		case "USER_SELECTED_GITHUB_CONNECTOR":
		case "GITHUB_CONNECTOR":
			return <IconBrandGithub className="h-4 w-4" />;
		case "USER_SELECTED_NOTION_CONNECTOR":
		case "NOTION_CONNECTOR":
			return <FileText className="h-4 w-4" />;
		case "USER_SELECTED_FILE":
		case "FILE":
			return <FileText className="h-4 w-4" />;
		default:
			return <Globe className="h-4 w-4" />;
	}
}

function SourceCard({ source }: { source: Source }) {
	const hasUrl = source.url && source.url.trim() !== "";

	return (
		<Card className="mb-3">
			<CardHeader className="pb-2">
				<div className="flex items-start justify-between gap-2">
					<CardTitle className="text-sm md:text-base font-medium leading-tight">
						{source.title}
					</CardTitle>
					{hasUrl && (
						<Button
							variant="ghost"
							size="sm"
							className="h-6 w-6 md:h-8 md:w-8 p-0 flex-shrink-0"
							onClick={() => window.open(source.url, "_blank")}
						>
							<ExternalLink className="h-3 w-3 md:h-4 md:w-4" />
						</Button>
					)}
				</div>
			</CardHeader>
			<CardContent className="pt-0">
				<CardDescription className="text-xs md:text-sm line-clamp-3 md:line-clamp-4 leading-relaxed">
					{source.description}
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
			if (
				item &&
				typeof item === "object" &&
				"nodes" in item &&
				Array.isArray(item.nodes)
			) {
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
			{} as Record<string, SourceNode[]>,
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

	const totalSources = sourceGroups.reduce(
		(acc, group) => acc + group.sources.length,
		0,
	);

	return (
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogTrigger asChild>
				<Button variant="outline" size="sm" className="w-fit">
					<FileText className="h-4 w-4 mr-2" />
					View Sources ({totalSources})
				</Button>
			</DialogTrigger>
			<DialogContent className="max-w-4xl md:h-[80vh] h-[90vh] w-[95vw] md:w-auto flex flex-col">
				<DialogHeader className="flex-shrink-0">
					<DialogTitle>Sources</DialogTitle>
				</DialogHeader>
				<Tabs
					defaultValue={sourceGroups[0]?.type}
					className="flex-1 flex flex-col min-h-0"
				>
					<div className="flex-shrink-0 w-full overflow-x-auto">
						<TabsList className="flex w-max min-w-full">
							{sourceGroups.map((group) => (
								<TabsTrigger
									key={group.type}
									value={group.type}
									className="flex items-center gap-2 whitespace-nowrap px-3 md:px-4"
								>
									{getSourceIcon(group.type)}
									<span className="truncate max-w-[100px] md:max-w-none">
										{group.name}
									</span>
									<Badge
										variant="secondary"
										className="ml-1 h-5 text-xs flex-shrink-0"
									>
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
							className="flex-1 min-h-0 mt-4"
						>
							<div className="h-full overflow-y-auto pr-2">
								<div className="space-y-3">
									{group.sources.map((source) => (
										<SourceCard key={source.id} source={source} />
									))}
								</div>
							</div>
						</TabsContent>
					))}
				</Tabs>
			</DialogContent>
		</Dialog>
	);
}
