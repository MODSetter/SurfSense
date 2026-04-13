import { useState, useRef } from "react";
import { Send, Paperclip, X, FileText, Image, File } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { cn } from "~/lib/utils";

export interface AttachedFile {
    /** File ID */
    id: string;
    /** File name */
    name: string;
    /** File type */
    type: string;
    /** File size in bytes */
    size: number;
    /** File object */
    file: File;
}

interface ChatInputProps {
    /** Callback when message is sent */
    onSend: (content: string, attachments?: AttachedFile[]) => void;
    /** Whether input is disabled */
    disabled?: boolean;
    /** Placeholder text */
    placeholder?: string;
    /** Whether to show attachment button */
    showAttachment?: boolean;
    /** Accepted file types */
    acceptedFileTypes?: string;
    /** Max file size in bytes (default 10MB) */
    maxFileSize?: number;
    /** Quick action suggestions */
    suggestions?: string[];
    /** Callback when suggestion is clicked */
    onSuggestionClick?: (suggestion: string) => void;
}

/**
 * Enhanced chat input with attachment support and suggestions
 *
 * Features:
 * - Text input with send button
 * - File attachment button
 * - Attached files preview
 * - Quick action suggestions
 * - Keyboard shortcuts (Enter to send)
 */
export function ChatInput({
    onSend,
    disabled,
    placeholder,
    showAttachment = true,
    acceptedFileTypes = ".pdf,.txt,.md,.json,.csv,image/*",
    maxFileSize = 10 * 1024 * 1024, // 10MB
    suggestions = [],
    onSuggestionClick,
}: ChatInputProps) {
    const [input, setInput] = useState("");
    const [attachments, setAttachments] = useState<AttachedFile[]>([]);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if ((input.trim() || attachments.length > 0) && !disabled) {
            onSend(input.trim(), attachments.length > 0 ? attachments : undefined);
            setInput("");
            setAttachments([]);
        }
    };

    const handleFileSelect = (files: FileList | null) => {
        if (!files) return;

        const newAttachments: AttachedFile[] = [];

        Array.from(files).forEach(file => {
            // Check file size
            if (file.size > maxFileSize) {
                console.warn(`File ${file.name} exceeds max size of ${maxFileSize / 1024 / 1024}MB`);
                return;
            }

            newAttachments.push({
                id: `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                name: file.name,
                type: file.type,
                size: file.size,
                file,
            });
        });

        setAttachments(prev => [...prev, ...newAttachments]);
    };

    const handleRemoveAttachment = (id: string) => {
        setAttachments(prev => prev.filter(a => a.id !== id));
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        handleFileSelect(e.dataTransfer.files);
    };

    const getFileIcon = (type: string) => {
        if (type.startsWith("image/")) return Image;
        if (type.includes("pdf") || type.includes("text")) return FileText;
        return File;
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="border-t">
            {/* Quick suggestions */}
            {suggestions.length > 0 && input.length === 0 && attachments.length === 0 && (
                <div className="px-3 pt-2 flex gap-2 flex-wrap">
                    {suggestions.slice(0, 3).map((suggestion, index) => (
                        <button
                            key={index}
                            className="text-xs px-2 py-1 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground transition-colors"
                            onClick={() => onSuggestionClick?.(suggestion)}
                        >
                            {suggestion}
                        </button>
                    ))}
                </div>
            )}

            {/* Attached files preview */}
            {attachments.length > 0 && (
                <div className="px-3 pt-2 flex gap-2 flex-wrap">
                    {attachments.map((attachment) => {
                        const FileIcon = getFileIcon(attachment.type);
                        return (
                            <div
                                key={attachment.id}
                                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-sm group"
                            >
                                <FileIcon className="h-3.5 w-3.5 text-muted-foreground" />
                                <span className="max-w-[100px] truncate">{attachment.name}</span>
                                <span className="text-xs text-muted-foreground">
                                    ({formatFileSize(attachment.size)})
                                </span>
                                <button
                                    onClick={() => handleRemoveAttachment(attachment.id)}
                                    className="ml-1 p-0.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Input form */}
            <form
                onSubmit={handleSubmit}
                className={cn(
                    "p-3 transition-colors",
                    dragOver && "bg-primary/5"
                )}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
            >
                <div className="flex items-end gap-2">
                    {/* Attachment button */}
                    {showAttachment && (
                        <>
                            <input
                                ref={fileInputRef}
                                type="file"
                                multiple
                                accept={acceptedFileTypes}
                                onChange={(e) => handleFileSelect(e.target.files)}
                                className="hidden"
                            />
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-9 w-9 flex-shrink-0"
                                onClick={() => fileInputRef.current?.click()}
                                disabled={disabled}
                                title="Attach files"
                            >
                                <Paperclip className="h-4 w-4" />
                            </Button>
                        </>
                    )}

                    {/* Text input */}
                    <div className="flex-1 relative">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSubmit(e);
                                }
                            }}
                            placeholder={placeholder || "Type a message..."}
                            disabled={disabled}
                            rows={1}
                            className={cn(
                                "w-full px-3 py-2 border rounded-md bg-background text-sm",
                                "focus:outline-none focus:ring-2 focus:ring-primary",
                                "resize-none min-h-[38px] max-h-[120px]",
                                "scrollbar-thin scrollbar-thumb-muted"
                            )}
                            style={{
                                height: "auto",
                                minHeight: "38px",
                            }}
                        />
                    </div>

                    {/* Send button */}
                    <Button
                        type="submit"
                        size="icon"
                        className="h-9 w-9 flex-shrink-0"
                        disabled={disabled || (!input.trim() && attachments.length === 0)}
                    >
                        <Send className="h-4 w-4" />
                    </Button>
                </div>

                {/* Drag hint */}
                {dragOver && (
                    <div className="absolute inset-0 flex items-center justify-center bg-primary/10 rounded-md border-2 border-dashed border-primary pointer-events-none">
                        <p className="text-sm text-primary font-medium">Drop files here</p>
                    </div>
                )}
            </form>
        </div>
    );
}
