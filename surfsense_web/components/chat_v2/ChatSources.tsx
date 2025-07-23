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
import { ExternalLink, FileText, Github, Globe } from "lucide-react";

interface Source {
    id: number;
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

function getSourceIcon(type: string) {
    switch (type) {
        case "GITHUB_CONNECTOR":
            return <Github className="h-4 w-4" />;
        case "NOTION_CONNECTOR":
            return <FileText className="h-4 w-4" />;
        case "FILE":
        case "USER_SELECTED_FILE":
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
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium truncate">
                        {source.title}
                    </CardTitle>
                    {hasUrl && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0"
                            onClick={() => window.open(source.url, "_blank")}
                        >
                            <ExternalLink className="h-3 w-3" />
                        </Button>
                    )}
                </div>
            </CardHeader>
            <CardContent className="pt-0">
                <CardDescription className="text-xs line-clamp-3">
                    {source.description}
                </CardDescription>
            </CardContent>
        </Card>
    );
}

export default function ChatSourcesDisplay({ message }: { message: Message }) {
    const [open, setOpen] = useState(false);
    const annotations = getAnnotationData(message, "SOURCES");

    // Flatten the nested array structure and ensure we have source groups
    const sourceGroups: SourceGroup[] =
        Array.isArray(annotations) && annotations.length > 0
            ? annotations
                  .flat()
                  .filter(
                      (group): group is SourceGroup =>
                          group !== null &&
                          group !== undefined &&
                          typeof group === "object" &&
                          "sources" in group &&
                          Array.isArray(group.sources)
                  )
            : [];

    if (sourceGroups.length === 0) {
        return null;
    }

    const totalSources = sourceGroups.reduce(
        (acc, group) => acc + group.sources.length,
        0
    );

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="w-fit">
                    <FileText className="h-4 w-4 mr-2" />
                    View Sources ({totalSources})
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl h-[80vh] flex flex-col">
                <DialogHeader className="flex-shrink-0">
                    <DialogTitle>Sources</DialogTitle>
                </DialogHeader>
                <Tabs
                    defaultValue={sourceGroups[0]?.type}
                    className="flex-1 flex flex-col min-h-0"
                >
                    <TabsList
                        className="grid w-full flex-shrink-0"
                        style={{
                            gridTemplateColumns: `repeat(${sourceGroups.length}, 1fr)`,
                        }}
                    >
                        {sourceGroups.map((group) => (
                            <TabsTrigger
                                key={group.type}
                                value={group.type}
                                className="flex items-center gap-2"
                            >
                                {getSourceIcon(group.type)}
                                <span className="truncate">{group.name}</span>
                                <Badge
                                    variant="secondary"
                                    className="ml-1 h-5 text-xs"
                                >
                                    {group.sources.length}
                                </Badge>
                            </TabsTrigger>
                        ))}
                    </TabsList>
                    {sourceGroups.map((group) => (
                        <TabsContent
                            key={group.type}
                            value={group.type}
                            className="flex-1 min-h-0 mt-4"
                        >
                            <div className="h-full overflow-y-auto pr-2">
                                <div className="space-y-3">
                                    {group.sources.map((source) => (
                                        <SourceCard
                                            key={source.id}
                                            source={source}
                                        />
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
