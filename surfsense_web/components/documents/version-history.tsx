"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, ChevronRight, Clock, Copy, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { toast } from "sonner";

interface DocumentVersionSummary {
	version_number: number;
	title: string;
	content_hash: string;
	created_at: string | null;
}

interface VersionHistoryProps {
	documentId: number;
	documentType: string;
}

const VERSION_DOCUMENT_TYPES = new Set(["LOCAL_FOLDER_FILE", "OBSIDIAN_CONNECTOR"]);

export function isVersionableType(documentType: string) {
	return VERSION_DOCUMENT_TYPES.has(documentType);
}

const DIALOG_CLASSES =
	"select-none max-w-[900px] w-[95vw] md:w-[90vw] h-[90vh] md:h-[80vh] max-h-[640px] flex flex-col md:flex-row p-0 gap-0 overflow-hidden [--card:var(--background)] dark:[--card:oklch(0.205_0_0)] dark:[--background:oklch(0.205_0_0)]";

export function VersionHistoryButton({ documentId, documentType }: VersionHistoryProps) {
	if (!isVersionableType(documentType)) return null;

	return (
		<Dialog>
			<DialogTrigger asChild>
				<Button variant="ghost" size="sm" className="gap-1.5 text-xs">
					<Clock className="h-3.5 w-3.5" />
					Versions
				</Button>
			</DialogTrigger>
			<DialogContent className={DIALOG_CLASSES}>
				<DialogTitle className="sr-only">Version History</DialogTitle>
				<VersionHistoryPanel documentId={documentId} />
			</DialogContent>
		</Dialog>
	);
}

export function VersionHistoryDialog({
	open,
	onOpenChange,
	documentId,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	documentId: number;
}) {
	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className={DIALOG_CLASSES}>
				<DialogTitle className="sr-only">Version History</DialogTitle>
				{open && <VersionHistoryPanel documentId={documentId} />}
			</DialogContent>
		</Dialog>
	);
}

function formatRelativeTime(dateStr: string): string {
	const now = Date.now();
	const then = new Date(dateStr).getTime();
	const diffMs = now - then;
	const diffMin = Math.floor(diffMs / 60_000);
	if (diffMin < 1) return "Just now";
	if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? "s" : ""} ago`;
	const diffHr = Math.floor(diffMin / 60);
	if (diffHr < 24) return `${diffHr} hour${diffHr !== 1 ? "s" : ""} ago`;
	return new Date(dateStr).toLocaleDateString(undefined, {
		weekday: "short",
		month: "short",
		day: "numeric",
		year: "numeric",
		hour: "numeric",
		minute: "2-digit",
	});
}

function VersionHistoryPanel({ documentId }: { documentId: number }) {
	const [versions, setVersions] = useState<DocumentVersionSummary[]>([]);
	const [loading, setLoading] = useState(true);
	const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
	const [versionContent, setVersionContent] = useState<string>("");
	const [contentLoading, setContentLoading] = useState(false);
	const [restoring, setRestoring] = useState(false);
	const [copied, setCopied] = useState(false);

	const loadVersions = useCallback(async () => {
		setLoading(true);
		try {
			const data = await documentsApiService.listDocumentVersions(documentId);
			setVersions(data as DocumentVersionSummary[]);
		} catch {
			toast.error("Failed to load version history");
		} finally {
			setLoading(false);
		}
	}, [documentId]);

	useEffect(() => {
		loadVersions();
	}, [loadVersions]);

	const handleSelectVersion = async (versionNumber: number) => {
		if (selectedVersion === versionNumber) return;
		setSelectedVersion(versionNumber);
		setContentLoading(true);
		try {
			const data = (await documentsApiService.getDocumentVersion(
				documentId,
				versionNumber
			)) as { source_markdown: string };
			setVersionContent(data.source_markdown || "");
		} catch {
			toast.error("Failed to load version content");
		} finally {
			setContentLoading(false);
		}
	};

	const handleRestore = async (versionNumber: number) => {
		setRestoring(true);
		try {
			await documentsApiService.restoreDocumentVersion(documentId, versionNumber);
			toast.success(`Restored version ${versionNumber}`);
			await loadVersions();
		} catch {
			toast.error("Failed to restore version");
		} finally {
			setRestoring(false);
		}
	};

	const handleCopy = () => {
		navigator.clipboard.writeText(versionContent);
		setCopied(true);
		setTimeout(() => setCopied(false), 2000);
	};

	if (loading) {
		return (
			<div className="flex flex-1 items-center justify-center">
				<Spinner size="lg" className="text-muted-foreground" />
			</div>
		);
	}

	if (versions.length === 0) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center text-muted-foreground">
				<p className="text-sm">No version history available yet</p>
				<p className="text-xs mt-1">Versions are created when file content changes</p>
			</div>
		);
	}

	const selectedVersionData = versions.find((v) => v.version_number === selectedVersion);

	return (
		<>
			{/* Left panel — version list */}
			<nav className="w-full md:w-[260px] shrink-0 flex flex-col border-b md:border-b-0 md:border-r border-border">
				<div className="px-4 pr-12 md:pr-4 pt-5 pb-2">
					<h2 className="text-sm font-semibold text-foreground">Version History</h2>
				</div>
				<div className="flex-1 overflow-y-auto p-2">
					<div className="flex flex-col gap-0.5">
						{versions.map((v) => (
							<button
								key={v.version_number}
								type="button"
								onClick={() => handleSelectVersion(v.version_number)}
								className={cn(
									"flex items-center gap-2 rounded-lg px-3 py-2.5 text-left transition-colors focus:outline-none focus-visible:outline-none w-full",
									selectedVersion === v.version_number
										? "bg-accent text-accent-foreground"
										: "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
								)}
							>
								<div className="flex-1 min-w-0 space-y-0.5">
									<p className="text-sm font-medium truncate">
										{v.created_at ? formatRelativeTime(v.created_at) : `Version ${v.version_number}`}
									</p>
									{v.title && (
										<p className="text-xs text-muted-foreground truncate">
											{v.title}
										</p>
									)}
								</div>
								<ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-50" />
							</button>
						))}
					</div>
				</div>
			</nav>

			{/* Right panel — content preview */}
			<div className="flex flex-1 flex-col overflow-hidden min-w-0">
				{selectedVersion !== null && selectedVersionData ? (
					<>
						<div className="flex items-center justify-between pl-6 pr-14 pt-5 pb-2">
							<h2 className="text-sm font-semibold truncate">
								{selectedVersionData.title || `Version ${selectedVersion}`}
							</h2>
							<div className="flex items-center gap-1.5 shrink-0">
								<Button
									variant="outline"
									size="sm"
									className="gap-1.5 text-xs"
									onClick={handleCopy}
									disabled={contentLoading || copied}
								>
									{copied ? (
										<Check className="h-3 w-3" />
									) : (
										<Copy className="h-3 w-3" />
									)}
									{copied ? "Copied" : "Copy"}
								</Button>
								<Button
									variant="outline"
									size="sm"
									className="gap-1.5 text-xs"
									disabled={restoring || contentLoading}
									onClick={() => handleRestore(selectedVersion)}
								>
									{restoring ? (
										<Spinner size="xs" />
									) : (
										<RotateCcw className="h-3 w-3" />
									)}
									Restore
								</Button>
							</div>
						</div>
						<Separator />
						<div className="flex-1 overflow-y-auto px-6 py-4">
							{contentLoading ? (
								<div className="flex items-center justify-center py-12">
									<Spinner size="sm" className="text-muted-foreground" />
								</div>
							) : (
								<pre className="text-sm whitespace-pre-wrap font-mono leading-relaxed text-foreground/90">
									{versionContent || "(empty)"}
								</pre>
							)}
						</div>
					</>
				) : (
					<div className="flex flex-1 items-center justify-center text-muted-foreground">
						<p className="text-sm">Select a version to preview</p>
					</div>
				)}
			</div>
		</>
	);
}
