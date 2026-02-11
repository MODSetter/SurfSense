"use client";

import { useAtomValue, useSetAtom } from "jotai";
import {
	CheckIcon,
	ChevronDownIcon,
	ClipboardIcon,
	FileTextIcon,
	XIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import {
	closeReportPanelAtom,
	reportPanelAtom,
} from "@/atoms/chat/report-panel.atom";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
} from "@/components/ui/drawer";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { useMediaQuery } from "@/hooks/use-media-query";
import { baseApiService } from "@/lib/apis/base-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";

/**
 * Zod schema for the report content API response
 */
const ReportContentResponseSchema = z.object({
	id: z.number(),
	title: z.string(),
	content: z.string().nullish(),
	report_metadata: z
		.object({
			status: z.enum(["ready", "failed"]).nullish(),
			error_message: z.string().nullish(),
			word_count: z.number().nullish(),
			char_count: z.number().nullish(),
			section_count: z.number().nullish(),
		})
		.nullish(),
});

type ReportContentResponse = z.infer<typeof ReportContentResponseSchema>;

/**
 * Shimmer loading skeleton for report panel
 */
function ReportPanelSkeleton() {
	return (
		<div className="space-y-6 p-6">
			{/* Title skeleton */}
			<div className="h-6 w-3/4 rounded-md bg-muted/60 animate-pulse" />

			{/* Paragraph 1 */}
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse" />
				<div className="h-3 w-[95%] rounded-md bg-muted/60 animate-pulse [animation-delay:100ms]" />
				<div className="h-3 w-[88%] rounded-md bg-muted/60 animate-pulse [animation-delay:200ms]" />
				<div className="h-3 w-[60%] rounded-md bg-muted/60 animate-pulse [animation-delay:300ms]" />
			</div>

			{/* Heading */}
			<div className="h-5 w-2/5 rounded-md bg-muted/60 animate-pulse [animation-delay:400ms]" />

			{/* Paragraph 2 */}
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse [animation-delay:500ms]" />
				<div className="h-3 w-[92%] rounded-md bg-muted/60 animate-pulse [animation-delay:600ms]" />
				<div className="h-3 w-[97%] rounded-md bg-muted/60 animate-pulse [animation-delay:700ms]" />
			</div>

			{/* Heading */}
			<div className="h-5 w-1/3 rounded-md bg-muted/60 animate-pulse [animation-delay:800ms]" />

			{/* Paragraph 3 */}
			<div className="space-y-2.5">
				<div className="h-3 w-[90%] rounded-md bg-muted/60 animate-pulse [animation-delay:900ms]" />
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse [animation-delay:1000ms]" />
				<div className="h-3 w-[75%] rounded-md bg-muted/60 animate-pulse [animation-delay:1100ms]" />
			</div>
		</div>
	);
}

/**
 * Inner content component used by both desktop panel and mobile drawer
 */
function ReportPanelContent({
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
	const [reportContent, setReportContent] =
		useState<ReportContentResponse | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [copied, setCopied] = useState(false);
	const [exporting, setExporting] = useState<"pdf" | "docx" | "md" | null>(null);

	// Fetch report content
	useEffect(() => {
		let cancelled = false;
		const fetchContent = async () => {
			setIsLoading(true);
			setError(null);
			try {
				const url = shareToken
					? `/api/v1/public/${shareToken}/reports/${reportId}/content`
					: `/api/v1/reports/${reportId}/content`;
				const rawData = await baseApiService.get<unknown>(url);
				if (cancelled) return;
				const parsed = ReportContentResponseSchema.safeParse(rawData);
				if (parsed.success) {
					// Check if the report was marked as failed in metadata
					if (parsed.data.report_metadata?.status === "failed") {
						setError(
							parsed.data.report_metadata?.error_message ||
								"Report generation failed"
						);
					} else {
						setReportContent(parsed.data);
					}
				} else {
					console.warn(
						"Invalid report content response:",
						parsed.error.issues
					);
					setError("Invalid response format");
				}
			} catch (err) {
				if (cancelled) return;
				console.error("Error fetching report content:", err);
				setError(
					err instanceof Error ? err.message : "Failed to load report"
				);
			} finally {
				if (!cancelled) setIsLoading(false);
			}
		};

		fetchContent();
		return () => {
			cancelled = true;
		};
	}, [reportId, shareToken]);

	// Copy markdown content
	const handleCopy = useCallback(async () => {
		if (!reportContent?.content) return;
		try {
			await navigator.clipboard.writeText(reportContent.content);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		} catch (err) {
			console.error("Failed to copy:", err);
		}
	}, [reportContent?.content]);

	// Export report
	const handleExport = useCallback(
		async (format: "pdf" | "docx" | "md") => {
			setExporting(format);
			const safeTitle =
				title.replace(/[^a-zA-Z0-9 _-]/g, "_").trim().slice(0, 80) ||
				"report";
			try {
				if (format === "md") {
					// Download markdown content directly as a .md file
					if (!reportContent?.content) return;
					const blob = new Blob([reportContent.content], {
						type: "text/markdown;charset=utf-8",
					});
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = `${safeTitle}.md`;
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
					URL.revokeObjectURL(url);
				} else {
					const response = await authenticatedFetch(
						`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/reports/${reportId}/export?format=${format}`,
						{ method: "GET" }
					);

					if (!response.ok) {
						throw new Error(`Export failed: ${response.status}`);
					}

					const blob = await response.blob();
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = `${safeTitle}.${format}`;
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
		[reportId, title, reportContent?.content]
	);


	if (isLoading) {
		return <ReportPanelSkeleton />;
	}

	if (error || !reportContent) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
				<div className="flex size-12 items-center justify-center rounded-full bg-muted">
					<FileTextIcon className="size-6 text-muted-foreground" />
				</div>
				<div>
					<p className="font-medium text-foreground">Failed to load report</p>
					<p className="text-sm text-muted-foreground mt-1">
						{error || "An unknown error occurred"}
					</p>
				</div>
			</div>
		);
	}

	return (
		<>
			{/* Action bar */}
			<div className="flex items-center justify-between px-4 py-2 shrink-0">
				<div className="flex items-center">
					<Button
						variant="outline"
						size="sm"
						onClick={handleCopy}
						className="h-7 min-w-[80px] px-2.5 py-4 text-xs gap-1.5 rounded-r-none border-r-0"
					>
						{copied ? (
							<CheckIcon className="size-3.5" />
						) : (
							<ClipboardIcon className="size-3.5" />
						)}
						{copied ? "Copied" : "Copy"}
					</Button>
					<DropdownMenu modal={insideDrawer ? false : undefined}>
						<DropdownMenuTrigger asChild>
							<Button
								variant="outline"
								size="sm"
								className="h-7 py-4 px-1.5 rounded-l-none"
							>
								<ChevronDownIcon className="size-3" />
								<span className="sr-only">Download options</span>
							</Button>
						</DropdownMenuTrigger>
					<DropdownMenuContent align="start" className={`min-w-[180px]${insideDrawer ? " z-[100]" : ""}`}>
						<DropdownMenuItem onClick={() => handleExport("md")}>
							Download Markdown
						</DropdownMenuItem>
						{/* PDF/DOCX export requires server-side conversion via authenticated endpoint.
						    Hide for public viewers who have no auth token. */}
						{!shareToken && (
							<>
								<DropdownMenuItem
									onClick={() => handleExport("pdf")}
									disabled={exporting !== null}
								>
									{exporting === "pdf" && (
										<Spinner size="xs" />
									)}
									Download PDF
								</DropdownMenuItem>
								<DropdownMenuItem
									onClick={() => handleExport("docx")}
									disabled={exporting !== null}
								>
									{exporting === "docx" && (
										<Spinner size="xs" />
									)}
									Download DOCX
								</DropdownMenuItem>
							</>
						)}
					</DropdownMenuContent>
					</DropdownMenu>
				</div>
				{onClose && (
					<Button
						variant="ghost"
						size="icon"
						onClick={onClose}
						className="size-7 shrink-0"
					>
						<XIcon className="size-4" />
						<span className="sr-only">Close report panel</span>
					</Button>
				)}
			</div>

			{/* Report content */}
			<div className="flex-1 overflow-y-auto scrollbar-thin">
				<div className="px-5 py-5">
				{reportContent.content ? (
						<MarkdownViewer content={reportContent.content} />
					) : (
						<p className="text-muted-foreground italic">
							No content available.
						</p>
					)}
				</div>
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

	return (
		<div
			ref={panelRef}
			className="flex w-[50%] max-w-[700px] min-w-[380px] flex-col border-l bg-background animate-in slide-in-from-right-4 duration-300 ease-out"
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

	return (
		<Drawer
			open={panelState.isOpen}
			onOpenChange={(open) => {
				if (!open) closePanel();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="h-[90vh] max-h-[90vh] z-80"
				overlayClassName="z-80"
			>
				<DrawerHandle />
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
 *
 * When open on desktop, the comments gutter is automatically suppressed
 * (handled via showCommentsGutterAtom in current-thread.atom.ts)
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

