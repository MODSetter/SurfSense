"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Check, ChevronDownIcon, Copy, Download, Pencil, XIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { closeReportPanelAtom, reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { EXPORT_FILE_EXTENSIONS, ExportDropdownItems } from "@/components/shared/ExportMenuItems";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { useMediaQuery } from "@/hooks/use-media-query";
import { baseApiService } from "@/lib/apis/base-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";

function ReportPanelSkeleton() {
	return (
		<div className="space-y-6 p-6">
			<div className="h-6 w-3/4 rounded-md bg-muted/60 animate-pulse" />
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse" />
				<div className="h-3 w-[95%] rounded-md bg-muted/60 animate-pulse [animation-delay:100ms]" />
				<div className="h-3 w-[88%] rounded-md bg-muted/60 animate-pulse [animation-delay:200ms]" />
				<div className="h-3 w-[60%] rounded-md bg-muted/60 animate-pulse [animation-delay:300ms]" />
			</div>
			<div className="h-5 w-2/5 rounded-md bg-muted/60 animate-pulse [animation-delay:400ms]" />
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse [animation-delay:500ms]" />
				<div className="h-3 w-[92%] rounded-md bg-muted/60 animate-pulse [animation-delay:600ms]" />
				<div className="h-3 w-[97%] rounded-md bg-muted/60 animate-pulse [animation-delay:700ms]" />
			</div>
			<div className="h-5 w-1/3 rounded-md bg-muted/60 animate-pulse [animation-delay:800ms]" />
			<div className="space-y-2.5">
				<div className="h-3 w-[90%] rounded-md bg-muted/60 animate-pulse [animation-delay:900ms]" />
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse [animation-delay:1000ms]" />
				<div className="h-3 w-[75%] rounded-md bg-muted/60 animate-pulse [animation-delay:1100ms]" />
			</div>
		</div>
	);
}

const PlateEditor = dynamic(
	() => import("@/components/editor/plate-editor").then((m) => ({ default: m.PlateEditor })),
	{ ssr: false, loading: () => <ReportPanelSkeleton /> }
);

const PdfViewer = dynamic(
	() => import("@/components/report-panel/pdf-viewer").then((m) => ({ default: m.PdfViewer })),
	{ ssr: false, loading: () => <ReportPanelSkeleton /> }
);

/**
 * Zod schema for a single version entry
 */
const VersionInfoSchema = z.object({
	id: z.number(),
	created_at: z.string().nullish(),
});

/**
 * Zod schema for the report content API response
 */
const ReportContentResponseSchema = z.object({
	id: z.number(),
	title: z.string(),
	content: z.string().nullish(),
	content_type: z.string().default("markdown"),
	report_metadata: z
		.object({
			status: z.enum(["ready", "failed"]).nullish(),
			error_message: z.string().nullish(),
			word_count: z.number().nullish(),
			char_count: z.number().nullish(),
			section_count: z.number().nullish(),
		})
		.nullish(),
	report_group_id: z.number().nullish(),
	versions: z.array(VersionInfoSchema).nullish(),
});

type ReportContentResponse = z.infer<typeof ReportContentResponseSchema>;
type VersionInfo = z.infer<typeof VersionInfoSchema>;

/**
 * Inner content component used by desktop panel, mobile drawer, and the layout right panel
 */
export function ReportPanelContent({
	reportId,
	title,
	onClose,
	insideDrawer = false,
	shareToken,
}: {
	reportId: number;
	title: string;
	onClose?: () => void;
	/** When true, adjusts dropdown behavior to work inside a Vaul drawer on mobile */
	insideDrawer?: boolean;
	/** When set, uses public endpoint for fetching report data (public shared chat) */
	shareToken?: string | null;
}) {
	const [reportContent, setReportContent] = useState<ReportContentResponse | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [copied, setCopied] = useState(false);
	const [exporting, setExporting] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);
	const copyTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
	const changeCountRef = useRef(0);

	useEffect(() => {
		return () => {
			if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
		};
	}, []);

	// Editor state — tracks the latest markdown from the Plate editor
	const [editedMarkdown, setEditedMarkdown] = useState<string | null>(null);
	const [isEditing, setIsEditing] = useState(false);

	// Read-only when public (shareToken) OR shared (SEARCH_SPACE visibility)
	const currentThreadState = useAtomValue(currentThreadAtom);
	const isReadOnly = !!shareToken || currentThreadState.visibility === "SEARCH_SPACE";

	// Version state
	const [activeReportId, setActiveReportId] = useState(reportId);
	const [versions, setVersions] = useState<VersionInfo[]>([]);

	// Reset active version when the external reportId changes (e.g. clicking a different card)
	useEffect(() => {
		setActiveReportId(reportId);
	}, [reportId]);

	// Fetch report content (re-runs when activeReportId changes for version switching)
	useEffect(() => {
		let cancelled = false;
		const fetchContent = async () => {
			setIsLoading(true);
			setError(null);
			try {
				const url = shareToken
					? `/api/v1/public/${shareToken}/reports/${activeReportId}/content`
					: `/api/v1/reports/${activeReportId}/content`;
				const rawData = await baseApiService.get<unknown>(url);
				if (cancelled) return;
				const parsed = ReportContentResponseSchema.safeParse(rawData);
				if (parsed.success) {
					// Check if the report was marked as failed in metadata
					if (parsed.data.report_metadata?.status === "failed") {
						setError(parsed.data.report_metadata?.error_message || "Report generation failed");
					} else {
						setReportContent(parsed.data);
						// Update versions from the response
						if (parsed.data.versions && parsed.data.versions.length > 0) {
							setVersions(parsed.data.versions);
						}
					}
				} else {
					console.warn("Invalid report content response:", parsed.error.issues);
					setError("Invalid response format");
				}
			} catch (err) {
				if (cancelled) return;
				console.error("Error fetching report content:", err);
				setError(err instanceof Error ? err.message : "Failed to load report");
			} finally {
				if (!cancelled) setIsLoading(false);
			}
		};

		fetchContent();
		return () => {
			cancelled = true;
		};
	}, [activeReportId, shareToken]);

	// The current markdown: use edited version if available, otherwise original
	const currentMarkdown = editedMarkdown ?? reportContent?.content ?? null;

	// Reset edited markdown when switching versions or reports
	useEffect(() => {
		setEditedMarkdown(null);
		setIsEditing(false);
		changeCountRef.current = 0;
	}, [activeReportId]);

	const handleReportMarkdownChange = useCallback(
		(nextMarkdown: string) => {
			if (!isEditing) return;
			changeCountRef.current += 1;
			// Plate may emit an initial normalize/serialize change on mount.
			if (changeCountRef.current <= 1) return;
			const savedMarkdown = reportContent?.content ?? "";
			setEditedMarkdown(nextMarkdown === savedMarkdown ? null : nextMarkdown);
		},
		[isEditing, reportContent?.content]
	);

	// Copy markdown content (uses latest editor content)
	const handleCopy = useCallback(async () => {
		if (!currentMarkdown) return;
		try {
			await navigator.clipboard.writeText(currentMarkdown);
			setCopied(true);
			if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
			copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
		} catch (err) {
			console.error("Failed to copy:", err);
		}
	}, [currentMarkdown]);

	const handleExport = useCallback(
		async (format: string) => {
			setExporting(format);
			const safeTitle =
				title
					.replace(/[^a-zA-Z0-9 _-]/g, "_")
					.trim()
					.slice(0, 80) || "report";
			const ext = EXPORT_FILE_EXTENSIONS[format] ?? format;
			try {
				if (format === "md") {
					if (!currentMarkdown) return;
					const blob = new Blob([currentMarkdown], {
						type: "text/markdown;charset=utf-8",
					});
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = `${safeTitle}.${ext}`;
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
					URL.revokeObjectURL(url);
				} else {
					const response = await authenticatedFetch(
						`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/reports/${activeReportId}/export?format=${format}`,
						{ method: "GET" }
					);

					if (!response.ok) {
						throw new Error(`Export failed: ${response.status}`);
					}

					const blob = await response.blob();
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = `${safeTitle}.${ext}`;
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
					URL.revokeObjectURL(url);
				}
			} catch (err) {
				console.error(`Export ${format} failed:`, err);
			} finally {
				setExporting(null);
			}
		},
		[activeReportId, title, currentMarkdown]
	);

	// Save edited report content
	const handleSave = useCallback(async () => {
		if (!currentMarkdown || !activeReportId) return false;
		setSaving(true);
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/reports/${activeReportId}/content`,
				{
					method: "PUT",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ content: currentMarkdown }),
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ detail: "Failed to save report" }));
				throw new Error(errorData.detail || "Failed to save report");
			}

			// Update local state to reflect saved content
			setReportContent((prev) => (prev ? { ...prev, content: currentMarkdown } : prev));
			setEditedMarkdown(null);
			toast.success("Report saved successfully");
			return true;
		} catch (err) {
			console.error("Error saving report:", err);
			toast.error(err instanceof Error ? err.message : "Failed to save report");
			return false;
		} finally {
			setSaving(false);
		}
	}, [activeReportId, currentMarkdown]);

	const activeVersionIndex = versions.findIndex((v) => v.id === activeReportId);
	const isPublic = !!shareToken;
	const isResume = reportContent?.content_type === "typst";
	const showReportEditingTier = !isResume;
	const hasUnsavedChanges = editedMarkdown !== null;
	const showDesktopHeader = !!onClose;

	const handleCancelEditing = useCallback(() => {
		setEditedMarkdown(null);
		changeCountRef.current = 0;
		setIsEditing(false);
	}, []);

	const exportButton = !isEditing && (
		<>
			{isResume ? (
				<Button
					variant="ghost"
					size="icon"
					className="size-6"
					onClick={() => handleExport("pdf")}
					disabled={isLoading || !reportContent?.content || exporting !== null}
				>
					{exporting === "pdf" ? <Spinner size="xs" /> : <Download className="size-3.5" />}
					<span className="sr-only">Download report</span>
				</Button>
			) : (
				<DropdownMenu modal={insideDrawer ? false : undefined}>
					<DropdownMenuTrigger asChild>
						<Button
							variant="ghost"
							size="icon"
							className="size-6"
							disabled={isLoading || !reportContent?.content}
						>
							<Download className="size-3.5" />
							<span className="sr-only">Export report</span>
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent
						align="end"
						className={`min-w-[200px] select-none${insideDrawer ? " z-[100]" : ""}`}
					>
						<ExportDropdownItems
							onExport={handleExport}
							exporting={exporting}
							showAllFormats={!shareToken}
						/>
					</DropdownMenuContent>
				</DropdownMenu>
			)}
		</>
	);

	const versionSwitcher = !isEditing && versions.length > 1 && (
		<DropdownMenu modal={insideDrawer ? false : undefined}>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" size="sm" className="h-6 gap-1 px-1.5 text-xs">
					v{activeVersionIndex + 1}
					<ChevronDownIcon className="size-3" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent
				align="end"
				className={`min-w-[120px] select-none${insideDrawer ? " z-[100]" : ""}`}
			>
				{versions.map((v, i) => (
					<DropdownMenuItem
						key={v.id}
						onClick={() => setActiveReportId(v.id)}
						className={v.id === activeReportId ? "bg-accent font-medium" : ""}
					>
						Version {i + 1}
					</DropdownMenuItem>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);

	const copyButton = !isEditing && showReportEditingTier && (
		<Button
			variant="ghost"
			size="icon"
			className="size-6"
			onClick={() => {
				void handleCopy();
			}}
			disabled={isLoading || !reportContent?.content}
		>
			{copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
			<span className="sr-only">{copied ? "Copied report content" : "Copy report content"}</span>
		</Button>
	);

	const editingActions =
		showReportEditingTier &&
		!isReadOnly &&
		(isEditing ? (
			<>
				<Button
					variant="ghost"
					size="sm"
					className="h-6 px-2 text-xs"
					onClick={handleCancelEditing}
					disabled={saving}
				>
					Cancel
				</Button>
				<Button
					variant="secondary"
					size="sm"
					className="relative h-6 w-[56px] px-0 text-xs"
					onClick={async () => {
						const saveSucceeded = await handleSave();
						if (saveSucceeded) setIsEditing(false);
					}}
					disabled={saving || !hasUnsavedChanges}
				>
					<span className={saving ? "opacity-0" : ""}>Save</span>
					{saving && <Spinner size="xs" className="absolute" />}
				</Button>
			</>
		) : (
			<Button
				variant="ghost"
				size="icon"
				className="size-6"
				onClick={() => {
					setEditedMarkdown(null);
					changeCountRef.current = 0;
					setIsEditing(true);
				}}
			>
				<Pencil className="size-3.5" />
				<span className="sr-only">Edit report</span>
			</Button>
		));

	return (
		<>
			{showDesktopHeader ? (
				<>
					{/* Header — matches the editor panel "File" header pattern */}
					<div className="flex h-14 items-center justify-between px-4 shrink-0">
						<h2 className="text-lg font-medium text-muted-foreground select-none">
							{isResume ? "Resume" : "Report"}
						</h2>
						{onClose && (
							<Button variant="ghost" size="icon" onClick={onClose} className="size-7 shrink-0">
								<XIcon className="size-4" />
								<span className="sr-only">Close report panel</span>
							</Button>
						)}
					</div>

					{!isResume && (
						<div className="flex h-10 items-center justify-between gap-2 border-t border-b px-4 shrink-0">
							<div className="min-w-0 flex-1">
								<p className="truncate text-sm text-muted-foreground">
									{reportContent?.title || title}
								</p>
							</div>
							<div className="flex items-center gap-1 shrink-0">
								{versionSwitcher}
								{exportButton}
								{copyButton}
								{editingActions}
							</div>
						</div>
					)}
				</>
			) : (
				!isResume && (
					<div className="flex h-14 items-center justify-between border-b px-4 shrink-0">
						<div className="flex-1 min-w-0">
							<h2 className="text-sm font-semibold truncate">{reportContent?.title || title}</h2>
						</div>
						<div className="flex items-center gap-1 shrink-0">
							{versionSwitcher}
							{exportButton}
							{copyButton}
							{editingActions}
						</div>
					</div>
				)
			)}

			{/* Report content — skeleton/error/viewer/editor shown only in this area */}
			<div className="flex-1 overflow-hidden">
				{isLoading ? (
					<ReportPanelSkeleton />
				) : error || !reportContent ? (
					<div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center select-none">
						<div>
							<p className="font-medium text-foreground">Failed to load report</p>
							<p className="text-sm text-red-500 mt-1">{error || "An unknown error occurred"}</p>
						</div>
					</div>
				) : reportContent.content_type === "typst" ? (
					<PdfViewer
						pdfUrl={`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}${shareToken ? `/api/v1/public/${shareToken}/reports/${activeReportId}/preview` : `/api/v1/reports/${activeReportId}/preview`}`}
						isPublic={isPublic}
						toolbarActions={
							<>
								{versionSwitcher}
								{exportButton}
							</>
						}
					/>
				) : reportContent.content ? (
					isReadOnly ? (
						<div className="h-full overflow-y-auto px-5 py-4">
							<MarkdownViewer content={reportContent.content} />
						</div>
					) : (
						<PlateEditor
							key={`report-${activeReportId}-${isEditing ? "editing" : "viewing"}`}
							preset="full"
							markdown={reportContent.content}
							onMarkdownChange={handleReportMarkdownChange}
							readOnly={!isEditing}
							placeholder="Report content..."
							editorVariant="default"
							allowModeToggle={false}
							reserveToolbarSpace
							defaultEditing={isEditing}
							className="[&_[role=toolbar]]:!bg-sidebar"
						/>
					)
				) : (
					<div className="px-5 py-5">
						<p className="text-muted-foreground italic">No content available.</p>
					</div>
				)}
			</div>
		</>
	);
}

/**
 * Desktop report panel — renders as a right-side flex sibling
 */
function DesktopReportPanel() {
	const panelState = useAtomValue(reportPanelAtom);
	const closePanel = useSetAtom(closeReportPanelAtom);
	const panelRef = useRef<HTMLDivElement>(null);

	// Close panel on Escape key
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				closePanel();
			}
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [closePanel]);

	if (!panelState.isOpen || !panelState.reportId) return null;

	const isPublic = !!panelState.shareToken;

	return (
		<div
			ref={panelRef}
			className={`flex w-[50%] max-w-[700px] min-w-[380px] flex-col border-l animate-in slide-in-from-right-4 duration-300 ease-out ${isPublic ? "bg-main-panel text-foreground" : "bg-sidebar text-sidebar-foreground"}`}
		>
			<ReportPanelContent
				reportId={panelState.reportId}
				title={panelState.title || "Report"}
				onClose={closePanel}
				shareToken={panelState.shareToken}
			/>
		</div>
	);
}

/**
 * Mobile report drawer — uses Vaul (same pattern as comment sheet)
 */
function MobileReportDrawer() {
	const panelState = useAtomValue(reportPanelAtom);
	const closePanel = useSetAtom(closeReportPanelAtom);

	if (!panelState.reportId) return null;

	const isPublic = !!panelState.shareToken;

	return (
		<Drawer
			open={panelState.isOpen}
			onOpenChange={(open) => {
				if (!open) closePanel();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className={`h-[90vh] max-h-[90vh] z-80 overflow-hidden ${isPublic ? "bg-main-panel" : "bg-sidebar"}`}
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">{panelState.title || "Report"}</DrawerTitle>
				<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
					<ReportPanelContent
						reportId={panelState.reportId}
						title={panelState.title || "Report"}
						insideDrawer
						shareToken={panelState.shareToken}
					/>
				</div>
			</DrawerContent>
		</Drawer>
	);
}

/**
 * ReportPanel — responsive report viewer
 *
 * On desktop (lg+): Renders as a right-side split panel (flex sibling to the chat thread)
 * On mobile/tablet: Renders as a Vaul bottom drawer
 */
export function ReportPanel() {
	const panelState = useAtomValue(reportPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	// Don't render anything if panel is not open
	if (!panelState.isOpen || !panelState.reportId) return null;

	if (isDesktop) {
		return <DesktopReportPanel />;
	}

	return <MobileReportDrawer />;
}

/**
 * MobileReportPanel — mobile-only report drawer
 *
 * Used in the dashboard chat page where the desktop report is handled
 * by the layout-level RightPanel instead.
 */
export function MobileReportPanel() {
	const panelState = useAtomValue(reportPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (isDesktop || !panelState.isOpen || !panelState.reportId) return null;

	return <MobileReportDrawer />;
}
