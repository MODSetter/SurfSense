"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import { Dot, FileTextIcon } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { z } from "zod";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
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
	parent_report_id: z.number().nullish(),
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
			status: z.enum(["ready", "failed"]).nullish(),
			error_message: z.string().nullish(),
			word_count: z.number().nullish(),
			section_count: z.number().nullish(),
		})
		.nullish(),
	report_group_id: z.number().nullish(),
	versions: z
		.array(
			z.object({
				id: z.number(),
				created_at: z.string().nullish(),
			})
		)
		.nullish(),
});

/**
 * Types derived from Zod schemas
 */
type GenerateReportArgs = z.infer<typeof GenerateReportArgsSchema>;
type GenerateReportResult = z.infer<typeof GenerateReportResultSchema>;

/**
 * Loading state component shown while report is being generated.
 * Matches the compact card layout of the completed ReportCard.
 */
function ReportGeneratingState({ topic }: { topic: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex w-full items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
					<FileTextIcon className="size-4 sm:size-6 text-primary" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{topic}
					</h3>
					<TextShimmerLoader text="Putting things together" size="sm" />
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
			<div className="flex items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-muted/60">
					<FileTextIcon className="size-4 sm:size-6 text-muted-foreground" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-muted-foreground text-sm sm:text-base leading-tight line-clamp-2">
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
	shareToken,
}: {
	reportId: number;
	title: string;
	wordCount?: number;
	/** When set, uses public endpoint for fetching report data */
	shareToken?: string | null;
}) {
	const openPanel = useSetAtom(openReportPanelAtom);
	const panelState = useAtomValue(reportPanelAtom);
	const [metadata, setMetadata] = useState<{
		title: string;
		wordCount: number | null;
		versionLabel: string | null;
	}>({ title, wordCount: wordCount ?? null, versionLabel: null });
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	// Fetch lightweight metadata (title + counts + version info)
	useEffect(() => {
		let cancelled = false;
		const fetchMetadata = async () => {
			setIsLoading(true);
			setError(null);
			try {
				const url = shareToken
					? `/api/v1/public/${shareToken}/reports/${reportId}/content`
					: `/api/v1/reports/${reportId}/content`;
				const rawData = await baseApiService.get<unknown>(url);
				if (cancelled) return;
				const parsed = ReportMetadataResponseSchema.safeParse(rawData);
				if (parsed.success) {
					// Check if report was marked as failed in metadata
					if (parsed.data.report_metadata?.status === "failed") {
						setError(
							parsed.data.report_metadata?.error_message ||
								"Report generation failed"
						);
					} else {
						// Determine version label from versions array
						let versionLabel: string | null = null;
						const versions = parsed.data.versions;
						if (versions && versions.length > 1) {
							const idx = versions.findIndex((v) => v.id === reportId);
							if (idx >= 0) {
								versionLabel = `version ${idx + 1}`;
							}
						}
						setMetadata({
							title: parsed.data.title || title,
							wordCount:
								parsed.data.report_metadata?.word_count ?? wordCount ?? null,
							versionLabel,
						});
					}
				}
			} catch {
				if (!cancelled) setError("No report found");
			} finally {
				if (!cancelled) setIsLoading(false);
			}
		};
		fetchMetadata();
		return () => {
			cancelled = true;
		};
	}, [reportId, title, wordCount, shareToken]);

	// Show non-clickable error card for any error (failed status, not found, etc.)
	if (!isLoading && error) {
		return <ReportErrorState title={title} error={error} />;
	}

	const isActive = panelState.isOpen && panelState.reportId === reportId;

	const handleOpen = () => {
		openPanel({
			reportId,
			title: metadata.title,
			wordCount: metadata.wordCount ?? undefined,
			shareToken,
		});
	};

	return (
		<div
			className={`my-4 overflow-hidden rounded-xl border bg-card transition-colors ${isActive ? "ring-1 ring-primary/50" : ""}`}
		>
			<button
				type="button"
				onClick={handleOpen}
				className="flex w-full items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6 text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:outline-none"
			>
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
					<FileTextIcon className="size-4 sm:size-6 text-primary" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{isLoading ? title : metadata.title}
					</h3>
					<p className="text-muted-foreground text-[10px] sm:text-xs mt-0.5">
						{isLoading ? (
							<span className="inline-block h-3 w-24 rounded bg-muted/60 animate-pulse" />
						) : (
							<>
								{metadata.wordCount != null &&
									`${metadata.wordCount.toLocaleString()} words`}
								{metadata.wordCount != null && metadata.versionLabel && <Dot className="inline size-4" />}
								{metadata.versionLabel}
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
		const params = useParams();
		const pathname = usePathname();
		const isPublicRoute = pathname?.startsWith("/public/");
		const shareToken = isPublicRoute && typeof params?.token === "string" ? params.token : null;

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
					shareToken={shareToken}
				/>
			);
		}

		// Fallback - missing required data
		return <ReportErrorState title={topic} error="Missing report ID" />;
	},
});
