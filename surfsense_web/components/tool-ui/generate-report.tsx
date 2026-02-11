"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import {
	FileTextIcon,
	Loader2Icon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { z } from "zod";
import {
	openReportPanelAtom,
	reportPanelAtom,
} from "@/atoms/chat/report-panel.atom";
import { baseApiService } from "@/lib/apis/base-api.service";

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

const ReportMetadataResponseSchema = z.object({
	id: z.number(),
	title: z.string(),
	report_metadata: z
		.object({
			word_count: z.number().nullish(),
			section_count: z.number().nullish(),
		})
		.nullish(),
});

/**
 * Types derived from Zod schemas
 */
type GenerateReportArgs = z.infer<typeof GenerateReportArgsSchema>;
type GenerateReportResult = z.infer<typeof GenerateReportResultSchema>;

/**
 * Shimmer line used in the skeleton loading state.
 * Each line has a staggered delay and random-ish width to mimic real paragraphs.
 */
function ShimmerLine({ width, delay }: { width: string; delay: string }) {
	return (
		<div
			className="h-2.5 rounded-md bg-muted/60"
			style={{
				width,
				animation: `pulse 2s cubic-bezier(0.4,0,0.6,1) infinite`,
				animationDelay: delay,
			}}
		/>
	);
}

/**
 * Loading state component shown while report is being generated.
 * Renders a card with a skeleton that looks like report content being written.
 */
function ReportGeneratingState({ topic }: { topic: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			{/* Header */}
			<div className="flex items-center gap-2 sm:gap-3 border-b bg-muted/30 px-4 py-3 sm:px-6 sm:py-4">
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight truncate">
						{topic}
					</h3>
					<div className="mt-1 flex items-center gap-1.5 text-muted-foreground">
						<Loader2Icon className="size-3 animate-spin" />
						<span className="text-[11px] sm:text-xs">Writing report…</span>
					</div>
				</div>
			</div>

			{/* Skeleton body – simulates paragraphs being written */}
			<div className="px-4 py-4 sm:px-6 sm:py-5 space-y-4 max-h-52 overflow-hidden relative">
				{/* "Heading" */}
				<ShimmerLine width="40%" delay="0ms" />

				{/* Paragraph 1 */}
				<div className="space-y-2">
					<ShimmerLine width="100%" delay="100ms" />
					<ShimmerLine width="92%" delay="150ms" />
					<ShimmerLine width="97%" delay="200ms" />
					<ShimmerLine width="60%" delay="250ms" />
				</div>

				{/* "Heading 2" */}
				<ShimmerLine width="35%" delay="300ms" />

				{/* Paragraph 2 */}
				<div className="space-y-2">
					<ShimmerLine width="95%" delay="350ms" />
					<ShimmerLine width="100%" delay="400ms" />
					<ShimmerLine width="88%" delay="450ms" />
				</div>

				{/* Bottom fade-out */}
				<div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-card to-transparent" />
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
 * Compact report card shown inline in the chat.
 * Clicking it opens the report in the right-side panel (desktop) or Vaul drawer (mobile).
 */
function ReportCard({
	reportId,
	title,
	wordCount,
}: {
	reportId: number;
	title: string;
	wordCount?: number;
}) {
	const openPanel = useSetAtom(openReportPanelAtom);
	const panelState = useAtomValue(reportPanelAtom);
	const [metadata, setMetadata] = useState<{
		title: string;
		wordCount: number | null;
		sectionCount: number | null;
	}>({ title, wordCount: wordCount ?? null, sectionCount: null });
	const [isLoading, setIsLoading] = useState(true);

	// Fetch lightweight metadata (title + counts only, no content)
	useEffect(() => {
		let cancelled = false;
		const fetchMetadata = async () => {
			setIsLoading(true);
			try {
				const rawData = await baseApiService.get<unknown>(
					`/api/v1/reports/${reportId}/content`
				);
				if (cancelled) return;
				const parsed = ReportMetadataResponseSchema.safeParse(rawData);
				if (parsed.success) {
					setMetadata({
						title: parsed.data.title || title,
						wordCount:
							parsed.data.report_metadata?.word_count ?? wordCount ?? null,
						sectionCount:
							parsed.data.report_metadata?.section_count ?? null,
					});
				}
			} catch {
				// Silently fail — we already have the title and word count from the tool result
			} finally {
				if (!cancelled) setIsLoading(false);
			}
		};
		fetchMetadata();
		return () => {
			cancelled = true;
		};
	}, [reportId, title, wordCount]);

	const isActive = panelState.isOpen && panelState.reportId === reportId;

	const handleOpen = () => {
		openPanel({
			reportId,
			title: metadata.title,
			wordCount: metadata.wordCount ?? undefined,
		});
	};

	return (
		<div
			className={`my-4 overflow-hidden rounded-xl border bg-card transition-colors ${isActive ? "ring-2 ring-primary/50" : ""}`}
		>
			<button
				type="button"
				onClick={handleOpen}
				className="flex w-full items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-3 sm:px-6 sm:py-4 text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:outline-none"
			>
				<div className="flex size-8 sm:size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
					<FileTextIcon className="size-4 sm:size-5 text-primary" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight truncate">
						{isLoading ? title : metadata.title}
					</h3>
					<p className="text-muted-foreground text-[10px] sm:text-xs mt-0.5">
						{isLoading ? (
							<span className="inline-block h-3 w-24 rounded bg-muted/60 animate-pulse" />
						) : (
							<>
								{metadata.wordCount != null &&
									`${metadata.wordCount.toLocaleString()} words`}
								{metadata.sectionCount != null &&
									` · ${metadata.sectionCount} sections`}
							</>
						)}
					</p>
				</div>
			</button>
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
				<ReportCard
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

