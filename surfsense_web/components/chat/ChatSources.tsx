"use client";

import { getAnnotationData, type Message } from "@llamaindex/chat-ui";
import { ExternalLink, FileText } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { SourceDetailSheet } from "./SourceDetailSheet";

interface Source {
	id: string;
	title: string;
	description: string;
	url: string;
	sourceType: string;
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
	// Handle USER_SELECTED_ prefix
	const normalizedType = type.startsWith("USER_SELECTED_")
		? type.replace("USER_SELECTED_", "")
		: type;
	return getConnectorIcon(normalizedType, "h-4 w-4");
}

function SourceCard({ source }: { source: Source }) {
	const hasUrl = source.url && source.url.trim() !== "";
	const chunkId = Number(source.id);
	const sourceType = source.sourceType;
	const [isOpen, setIsOpen] = useState(false);

	// Clean up the description for better display
	const cleanDescription = source.description
		.replace(/## Metadata\n\n/g, "")
		.replace(/\n+/g, " ")
		.trim();

	const handleUrlClick = (e: React.MouseEvent, url: string) => {
		e.preventDefault();
		e.stopPropagation();
		window.open(url, "_blank", "noopener,noreferrer");
	};

	return (
		<SourceDetailSheet
			open={isOpen}
			onOpenChange={setIsOpen}
			chunkId={chunkId}
			sourceType={sourceType}
			title={source.title}
			description={source.description}
			url={source.url}
		>
			<SheetTrigger asChild>
				<Card className="border-muted hover:border-muted-foreground/20 transition-colors cursor-pointer">
					<CardHeader className="pb-3 pt-3">
						<div className="flex items-start justify-between gap-2">
							<CardTitle className="text-sm font-medium leading-tight line-clamp-2 flex-1">
								{source.title}
							</CardTitle>
							<div className="flex items-center gap-1 flex-shrink-0">
								<Badge variant="secondary" className="text-[10px] h-5 px-2 font-mono">
									#{chunkId}
								</Badge>
								{hasUrl && (
									<Button
										variant="ghost"
										size="sm"
										className="h-7 w-7 p-0 flex-shrink-0 hover:bg-muted"
										onClick={(e) => handleUrlClick(e, source.url)}
									>
										<ExternalLink className="h-3.5 w-3.5" />
									</Button>
								)}
							</div>
						</div>
					</CardHeader>
					<CardContent className="pt-0 pb-3">
						<CardDescription className="text-xs line-clamp-3 leading-relaxed text-muted-foreground">
							{cleanDescription}
						</CardDescription>
					</CardContent>
				</Card>
			</SheetTrigger>
		</SourceDetailSheet>
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
						sourceType: sourceType,
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
