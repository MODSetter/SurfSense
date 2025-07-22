"use client";

import { ChatInput } from "@llamaindex/chat-ui";
import { FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Suspense, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useDocuments, Document } from "@/hooks/use-documents";
import { DocumentsDataTable } from "@/components/chat_v2/DocumentsDataTable";
import { ResearchMode } from "@/components/chat";
import React from "react";

const DocumentSelector = React.memo(
    ({
        onSelectionChange,
        selectedDocuments = [],
    }: {
        onSelectionChange?: (documents: Document[]) => void;
        selectedDocuments?: Document[];
    }) => {
        const { search_space_id } = useParams();
        const [isOpen, setIsOpen] = useState(false);

        const { documents, loading, isLoaded, fetchDocuments } = useDocuments(
            Number(search_space_id)
        );

        const handleOpenChange = useCallback(
            (open: boolean) => {
                setIsOpen(open);
                if (open && !isLoaded) {
                    fetchDocuments();
                }
            },
            [fetchDocuments, isLoaded]
        );

        const handleSelectionChange = useCallback(
            (documents: Document[]) => {
                onSelectionChange?.(documents);
            },
            [onSelectionChange]
        );

        const handleDone = useCallback(() => {
            setIsOpen(false);
        }, [selectedDocuments]);

        const selectedCount = selectedDocuments.length;

        return (
            <Dialog open={isOpen} onOpenChange={handleOpenChange}>
                <DialogTrigger asChild>
                    <Button variant="outline" className="relative">
                        <FolderOpen className="w-4 h-4" />
                        {selectedCount > 0 && (
                            <span className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center">
                                {selectedCount}
                            </span>
                        )}
                    </Button>
                </DialogTrigger>

                <DialogContent className="max-w-[95vw] md:max-w-5xl h-[90vh] md:h-[85vh] p-0 flex flex-col">
                    <div className="flex flex-col h-full">
                        <div className="px-4 md:px-6 py-4 border-b flex-shrink-0">
                            <DialogTitle className="text-lg md:text-xl">
                                Select Documents
                            </DialogTitle>
                            <DialogDescription className="mt-1 text-sm">
                                Choose documents to include in your research
                                context
                            </DialogDescription>
                        </div>

                        <div className="flex-1 min-h-0 p-4 md:p-6">
                            {loading ? (
                                <div className="flex items-center justify-center h-full">
                                    <div className="text-center space-y-2">
                                        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto" />
                                        <p className="text-sm text-muted-foreground">
                                            Loading documents...
                                        </p>
                                    </div>
                                </div>
                            ) : isLoaded ? (
                                <DocumentsDataTable
                                    documents={documents}
                                    onSelectionChange={handleSelectionChange}
                                    onDone={handleDone}
                                    initialSelectedDocuments={selectedDocuments}
                                />
                            ) : null}
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        );
    }
);

const SearchModeSelector = ({
    searchMode,
    onSearchModeChange,
}: {
    searchMode?: "DOCUMENTS" | "CHUNKS";
    onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
}) => {
    return (
        <div className="flex items-center gap-1 sm:gap-2">
            <span className="text-xs text-muted-foreground hidden sm:block">
                Scope:
            </span>
            <div className="flex rounded-md border">
                <Button
                    variant={searchMode === "DOCUMENTS" ? "default" : "ghost"}
                    size="sm"
                    className="rounded-r-none border-r h-8 px-2 sm:px-3 text-xs"
                    onClick={() => onSearchModeChange?.("DOCUMENTS")}
                >
                    <span className="hidden sm:inline">Documents</span>
                    <span className="sm:hidden">Docs</span>
                </Button>
                <Button
                    variant={searchMode === "CHUNKS" ? "default" : "ghost"}
                    size="sm"
                    className="rounded-l-none h-8 px-2 sm:px-3 text-xs"
                    onClick={() => onSearchModeChange?.("CHUNKS")}
                >
                    Chunks
                </Button>
            </div>
        </div>
    );
};

const ResearchModeSelector = ({
    researchMode,
    onResearchModeChange,
}: {
    researchMode?: ResearchMode;
    onResearchModeChange?: (mode: ResearchMode) => void;
}) => {
    const researchModeLabels: Record<ResearchMode, string> = {
        QNA: "Q&A",
        REPORT_GENERAL: "General Report",
        REPORT_DEEP: "Deep Report",
        REPORT_DEEPER: "Deeper Report",
    };

    const researchModeShortLabels: Record<ResearchMode, string> = {
        QNA: "Q&A",
        REPORT_GENERAL: "General",
        REPORT_DEEP: "Deep",
        REPORT_DEEPER: "Deeper",
    };

    return (
        <div className="flex items-center gap-1 sm:gap-2">
            <span className="text-xs text-muted-foreground hidden sm:block">
                Mode:
            </span>
            <Select
                value={researchMode}
                onValueChange={(value) =>
                    onResearchModeChange?.(value as ResearchMode)
                }
            >
                <SelectTrigger className="w-auto min-w-[80px] sm:min-w-[120px] h-8 text-xs">
                    <SelectValue placeholder="Mode" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="QNA">Q&A</SelectItem>
                    <SelectItem value="REPORT_GENERAL">
                        <span className="hidden sm:inline">General Report</span>
                        <span className="sm:hidden">General</span>
                    </SelectItem>
                    <SelectItem value="REPORT_DEEP">
                        <span className="hidden sm:inline">Deep Report</span>
                        <span className="sm:hidden">Deep</span>
                    </SelectItem>
                    <SelectItem value="REPORT_DEEPER">
                        <span className="hidden sm:inline">Deeper Report</span>
                        <span className="sm:hidden">Deeper</span>
                    </SelectItem>
                </SelectContent>
            </Select>
        </div>
    );
};

const CustomChatInputOptions = ({
    onDocumentSelectionChange,
    selectedDocuments,
    searchMode,
    onSearchModeChange,
    researchMode,
    onResearchModeChange,
}: {
    onDocumentSelectionChange?: (documents: Document[]) => void;
    selectedDocuments?: Document[];
    searchMode?: "DOCUMENTS" | "CHUNKS";
    onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
    researchMode?: ResearchMode;
    onResearchModeChange?: (mode: ResearchMode) => void;
}) => {
    return (
        <div className="flex flex-wrap gap-2 sm:gap-3 items-center justify-start">
            <Suspense fallback={<div>Loading...</div>}>
                <DocumentSelector
                    onSelectionChange={onDocumentSelectionChange}
                    selectedDocuments={selectedDocuments}
                />
            </Suspense>
            <SearchModeSelector
                searchMode={searchMode}
                onSearchModeChange={onSearchModeChange}
            />
            <ResearchModeSelector
                researchMode={researchMode}
                onResearchModeChange={onResearchModeChange}
            />
        </div>
    );
};

export const CustomChatInput = ({
    onDocumentSelectionChange,
    selectedDocuments,
    searchMode,
    onSearchModeChange,
    researchMode,
    onResearchModeChange,
}: {
    onDocumentSelectionChange?: (documents: Document[]) => void;
    selectedDocuments?: Document[];
    searchMode?: "DOCUMENTS" | "CHUNKS";
    onSearchModeChange?: (mode: "DOCUMENTS" | "CHUNKS") => void;
    researchMode?: ResearchMode;
    onResearchModeChange?: (mode: ResearchMode) => void;
}) => {
    return (
        <ChatInput>
            <ChatInput.Form className="flex gap-2">
                <ChatInput.Field className="flex-1" />
                <ChatInput.Submit />
            </ChatInput.Form>
            <CustomChatInputOptions
                onDocumentSelectionChange={onDocumentSelectionChange}
                selectedDocuments={selectedDocuments}
                searchMode={searchMode}
                onSearchModeChange={onSearchModeChange}
                researchMode={researchMode}
                onResearchModeChange={onResearchModeChange}
            />
        </ChatInput>
    );
};
