"use client";

import {
    ChatSection,
    ChatHandler,
    ChatInput,
    ChatCanvas,
    ChatMessages,
} from "@llamaindex/chat-ui";
import { Button } from "../ui/button";
import { FolderOpen } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "../ui/dialog";
import { Suspense, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useDocuments, DocumentType, Document } from "@/hooks/use-documents";
import { DocumentsDataTable } from "./DocumentsDataTable";
import React from "react";

interface ChatInterfaceProps {
    handler: ChatHandler;
    onDocumentSelectionChange?: (documents: Document[]) => void;
    selectedDocuments?: Document[];
}

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

const CustomChatInputOptions = ({
    onDocumentSelectionChange,
    selectedDocuments,
}: {
    onDocumentSelectionChange?: (documents: Document[]) => void;
    selectedDocuments?: Document[];
}) => {
    return (
        <div className="flex flex-row gap-2">
            <Suspense fallback={<div>Loading...</div>}>
                <DocumentSelector
                    onSelectionChange={onDocumentSelectionChange}
                    selectedDocuments={selectedDocuments}
                />
            </Suspense>
        </div>
    );
};

const CustomChatInput = ({
    onDocumentSelectionChange,
    selectedDocuments,
}: {
    onDocumentSelectionChange?: (documents: Document[]) => void;
    selectedDocuments?: Document[];
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
            />
        </ChatInput>
    );
};

export default function ChatInterface({
    handler,
    onDocumentSelectionChange,
    selectedDocuments = [],
}: ChatInterfaceProps) {
    return (
        <ChatSection handler={handler} className="flex h-full">
            <div className="flex flex-1 flex-col">
                <ChatMessages className="flex-1">
                    <ChatMessages.List className="p-4">
                        {/* Custom message rendering */}
                    </ChatMessages.List>
                    <ChatMessages.Loading />
                </ChatMessages>

                <div className="border-t p-4">
                    <CustomChatInput
                        onDocumentSelectionChange={onDocumentSelectionChange}
                        selectedDocuments={selectedDocuments}
                    />
                </div>
            </div>

            <ChatCanvas className="w-1/2 border-l" />
        </ChatSection>
    );
}
