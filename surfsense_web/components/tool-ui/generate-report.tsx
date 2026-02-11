"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	CheckIcon,
	ClipboardIcon,
	DownloadIcon,
	FileTextIcon,
	Loader2Icon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { baseApiService } from "@/lib/apis/base-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";

/**
 * Zod schemas for runtime validation
 */
const GenerateReportArgsSchema = z.object({
	topic: z.string(),
	source_content: z.string(),
	report_style: z.string().nullish(),
	user_instructions: z.string().nullish(),
});

const GenerateReportResultSchema = z.object({
	status: z.enum(["ready", "failed"]),
	report_id: z.number().nullish(),
	title: z.string().nullish(),
	word_count: z.number().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});

const ReportContentResponseSchema = z.object({
	id: z.number(),
	title: z.string(),
	content: z.string().nullish(),
	report_metadata: z
		.object({
			sections: z
				.array(
					z.object({
						level: z.number(),
						title: z.string(),
					})
				)
				.nullish(),
			word_count: z.number().nullish(),
			char_count: z.number().nullish(),
			section_count: z.number().nullish(),
		})
		.nullish(),
});

/**
 * Types derived from Zod schemas
 */
type GenerateReportArgs = z.infer<typeof GenerateReportArgsSchema>;
type GenerateReportResult = z.infer<typeof GenerateReportResultSchema>;
type ReportContentResponse = z.infer<typeof ReportContentResponseSchema>;

/**
 * Loading state component shown while report is being generated
 */
function ReportGeneratingState({ topic }: { topic: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="relative shrink-0">
					<div className="flex size-12 sm:size-16 items-center justify-center rounded-full bg-primary/20">
						<FileTextIcon className="size-6 sm:size-8 text-primary" />
					</div>
					<div className="absolute inset-1 animate-ping rounded-full bg-primary/20" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-lg leading-tight truncate">
						{topic}
					</h3>
					<div className="mt-1.5 sm:mt-2 flex items-center gap-1.5 sm:gap-2 text-muted-foreground">
						<Spinner size="sm" className="size-3 sm:size-4" />
						<span className="text-xs sm:text-sm">
							Generating report. This may take a moment...
						</span>
					</div>
					<div className="mt-2 sm:mt-3">
						<div className="h-1 sm:h-1.5 w-full overflow-hidden rounded-full bg-primary/10">
							<div className="h-full w-1/3 animate-pulse rounded-full bg-primary" />
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}

/**
 * Error state component shown when report generation fails
 */
function ReportErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-3 sm:px-6 sm:py-4">
				<div className="flex size-8 sm:size-10 shrink-0 items-center justify-center rounded-lg bg-muted/60">
					<FileTextIcon className="size-4 sm:size-5 text-muted-foreground/50" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-muted-foreground text-sm sm:text-base leading-tight truncate">
						{title}
					</h3>
					<p className="text-muted-foreground/60 text-[11px] sm:text-xs mt-0.5 truncate">
						{error}
					</p>
				</div>
			</div>
		</div>
	);
}

/**
 * Report viewer component that fetches and renders the full Markdown report
 */
function ReportViewer({
	reportId,
	title,
	wordCount,
}: {
	reportId: number;
	title: string;
	wordCount?: number;
}) {
	const [reportContent, setReportContent] = useState<ReportContentResponse | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [copied, setCopied] = useState(false);
	const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);

	// Fetch report content
	useEffect(() => {
		const fetchContent = async () => {
			setIsLoading(true);
			setError(null);
			try {
				const rawData = await baseApiService.get<unknown>(
					`/api/v1/reports/${reportId}/content`
				);
				const parsed = ReportContentResponseSchema.safeParse(rawData);
				if (parsed.success) {
					setReportContent(parsed.data);
				} else {
					console.warn("Invalid report content response:", parsed.error.issues);
					setError("Invalid response format");
				}
			} catch (err) {
				console.error("Error fetching report content:", err);
				setError(err instanceof Error ? err.message : "Failed to load report");
			} finally {
				setIsLoading(false);
			}
		};

		fetchContent();
	}, [reportId]);

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
		async (format: "pdf" | "docx") => {
			setExporting(format);
			try {
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
				a.download = `${title.replace(/[^a-zA-Z0-9 _-]/g, "_").trim().slice(0, 80) || "report"}.${format}`;
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);
			} catch (err) {
				console.error(`Export ${format} failed:`, err);
			} finally {
				setExporting(null);
			}
		},
		[reportId, title]
	);

	if (isLoading) {
		return (
			<div className="my-4 overflow-hidden rounded-xl border bg-muted/30 p-4 sm:p-6">
				<div className="flex items-center gap-3 sm:gap-4">
					<div className="flex size-12 sm:size-16 shrink-0 items-center justify-center rounded-full bg-primary/10">
						<FileTextIcon className="size-6 sm:size-8 text-primary/50" />
					</div>
					<div className="flex-1 min-w-0">
						<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight">
							{title}
						</h3>
						<div className="mt-1.5 sm:mt-2 flex items-center gap-1.5 sm:gap-2 text-muted-foreground">
							<Spinner size="sm" className="size-3 sm:size-4" />
							<span className="text-xs sm:text-sm">Loading report...</span>
						</div>
					</div>
				</div>
			</div>
		);
	}

	if (error || !reportContent) {
		return <ReportErrorState title={title} error={error || "Failed to load report"} />;
	}

	const displayWordCount =
		wordCount ?? reportContent.report_metadata?.word_count ?? null;

	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			{/* Header */}
			<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b bg-muted/30 px-4 py-3 sm:px-6 sm:py-4">
				<div className="flex items-center gap-2 sm:gap-3 min-w-0">
					<div className="flex size-8 sm:size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
						<FileTextIcon className="size-4 sm:size-5 text-primary" />
					</div>
					<div className="min-w-0">
						<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight truncate">
							{reportContent.title || title}
						</h3>
						{displayWordCount != null && (
							<p className="text-muted-foreground text-[10px] sm:text-xs mt-0.5">
								{displayWordCount.toLocaleString()} words
								{reportContent.report_metadata?.section_count
									? ` · ${reportContent.report_metadata.section_count} sections`
									: ""}
							</p>
						)}
					</div>
				</div>

				{/* Action buttons */}
				<div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
					<Button
						variant="ghost"
						size="sm"
						onClick={handleCopy}
						className="h-7 sm:h-8 px-2 sm:px-3 text-xs"
					>
						{copied ? (
							<CheckIcon className="size-3.5 mr-1" />
						) : (
							<ClipboardIcon className="size-3.5 mr-1" />
						)}
						{copied ? "Copied" : "Copy MD"}
					</Button>
					<Button
						variant="outline"
						size="sm"
						onClick={() => handleExport("pdf")}
						disabled={exporting !== null}
						className="h-7 sm:h-8 px-2 sm:px-3 text-xs"
					>
						{exporting === "pdf" ? (
							<Loader2Icon className="size-3.5 mr-1 animate-spin" />
						) : (
							<DownloadIcon className="size-3.5 mr-1" />
						)}
						PDF
					</Button>
					<Button
						variant="outline"
						size="sm"
						onClick={() => handleExport("docx")}
						disabled={exporting !== null}
						className="h-7 sm:h-8 px-2 sm:px-3 text-xs"
					>
						{exporting === "docx" ? (
							<Loader2Icon className="size-3.5 mr-1 animate-spin" />
						) : (
							<DownloadIcon className="size-3.5 mr-1" />
						)}
						DOCX
					</Button>
				</div>
			</div>

			{/* Markdown content */}
			<div className="px-4 py-4 sm:px-6 sm:py-5 overflow-x-auto">
				{reportContent.content ? (
					<MarkdownViewer content={reportContent.content} />
				) : (
					<p className="text-muted-foreground italic">No content available.</p>
				)}
			</div>
		</div>
	);
}

/**
 * Generate Report Tool UI Component
 *
 * This component is registered with assistant-ui to render custom UI
 * when the generate_report tool is called by the agent.
 *
 * Unlike podcast (which uses polling), the report is generated inline
 * and the result contains status: "ready" immediately.
 */
export const GenerateReportToolUI = makeAssistantToolUI<
	GenerateReportArgs,
	GenerateReportResult
>({
	toolName: "generate_report",
	render: function GenerateReportUI({ args, result, status }) {
		const topic = args.topic || "Report";

		// Loading state - tool is still running (LLM generating report)
		if (status.type === "running" || status.type === "requires-action") {
			return <ReportGeneratingState topic={topic} />;
		}

		// Incomplete/cancelled state
		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return (
					<div className="my-4 rounded-xl border border-muted p-3 sm:p-4 text-muted-foreground">
						<p className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
							<FileTextIcon className="size-3.5 sm:size-4" />
							<span className="line-through">Report generation cancelled</span>
						</p>
					</div>
				);
			}
			if (status.reason === "error") {
				return (
					<ReportErrorState
						title={topic}
						error={typeof status.error === "string" ? status.error : "An error occurred"}
					/>
				);
			}
		}

		// No result yet
		if (!result) {
			return <ReportGeneratingState topic={topic} />;
		}

		// Failed result
		if (result.status === "failed") {
			return <ReportErrorState title={result.title || topic} error={result.error || "Generation failed"} />;
		}

		// Ready with report_id
		if (result.status === "ready" && result.report_id) {
			return (
				<ReportViewer
					reportId={result.report_id}
					title={result.title || topic}
					wordCount={result.word_count ?? undefined}
				/>
			);
		}

		// Fallback - missing required data
		return <ReportErrorState title={topic} error="Missing report ID" />;
	},
});

