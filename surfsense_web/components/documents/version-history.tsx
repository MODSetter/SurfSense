"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Sheet,
	SheetContent,
	SheetHeader,
	SheetTitle,
	SheetTrigger,
} from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
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

export function VersionHistoryButton({ documentId, documentType }: VersionHistoryProps) {
	const showVersionHistory = documentType === "LOCAL_FOLDER_FILE" || documentType === "OBSIDIAN_CONNECTOR";
	if (!showVersionHistory) return null;

	return (
		<Sheet>
			<SheetTrigger asChild>
				<Button variant="ghost" size="sm" className="gap-1.5 text-xs">
					<Clock className="h-3.5 w-3.5" />
					Versions
				</Button>
			</SheetTrigger>
			<SheetContent className="w-[400px] sm:w-[540px]">
				<SheetHeader>
					<SheetTitle>Version History</SheetTitle>
				</SheetHeader>
				<VersionHistoryPanel documentId={documentId} />
			</SheetContent>
		</Sheet>
	);
}

function VersionHistoryPanel({ documentId }: { documentId: number }) {
	const [versions, setVersions] = useState<DocumentVersionSummary[]>([]);
	const [loading, setLoading] = useState(true);
	const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
	const [versionContent, setVersionContent] = useState<string>("");
	const [contentLoading, setContentLoading] = useState(false);
	const [restoring, setRestoring] = useState(false);

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

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="lg" className="text-muted-foreground" />
			</div>
		);
	}

	if (versions.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
				<Clock className="h-8 w-8 mb-2 opacity-50" />
				<p className="text-sm">No version history available yet.</p>
				<p className="text-xs mt-1">Versions are created when file content changes.</p>
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-4 pt-4 h-full">
			<div className="flex-1 overflow-y-auto space-y-2">
				{versions.map((v) => (
					<div
						key={v.version_number}
						className={`rounded-lg border p-3 cursor-pointer transition-colors ${
							selectedVersion === v.version_number
								? "border-primary bg-primary/5"
								: "border-border hover:border-primary/50"
						}`}
						onClick={() => handleSelectVersion(v.version_number)}
					>
						<div className="flex items-center justify-between">
							<div className="space-y-1">
								<p className="text-sm font-medium">Version {v.version_number}</p>
								{v.created_at && (
									<p className="text-xs text-muted-foreground">
										{new Date(v.created_at).toLocaleString()}
									</p>
								)}
								{v.title && (
									<p className="text-xs text-muted-foreground truncate max-w-[200px]">
										{v.title}
									</p>
								)}
							</div>
							<Button
								variant="outline"
								size="sm"
								className="shrink-0 gap-1"
								disabled={restoring}
								onClick={(e) => {
									e.stopPropagation();
									handleRestore(v.version_number);
								}}
							>
								<RotateCcw className="h-3 w-3" />
								Restore
							</Button>
						</div>
					</div>
				))}
			</div>

			{selectedVersion !== null && (
				<div className="border-t pt-4 max-h-[40vh] overflow-y-auto">
					<h4 className="text-sm font-medium mb-2">
						Preview — Version {selectedVersion}
					</h4>
					{contentLoading ? (
						<div className="flex items-center justify-center py-6">
							<Spinner size="sm" />
						</div>
					) : (
						<pre className="text-xs whitespace-pre-wrap font-mono bg-muted/50 rounded-lg p-3 max-h-[30vh] overflow-y-auto">
							{versionContent || "(empty)"}
						</pre>
					)}
				</div>
			)}
		</div>
	);
}
