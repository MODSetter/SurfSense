"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import { Dot } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { openReportPanelAtom, reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { useMediaQuery } from "@/hooks/use-media-query";
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

const ReportContentResponseSchema = z.object({
	id: z.number(),
	title: z.string(),
	content: z.string().nullish(),
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

function ContentSkeleton() {
	return (
		<div className="h-[7rem] space-y-2">
			<div className="h-3 w-full rounded bg-muted/60 animate-pulse" />
			<div className="h-3 w-[92%] rounded bg-muted/60 animate-pulse [animation-delay:100ms]" />
			<div className="h-3 w-[75%] rounded bg-muted/60 animate-pulse [animation-delay:200ms]" />
			<div className="h-3 w-[85%] rounded bg-muted/60 animate-pulse [animation-delay:300ms]" />
			<div className="h-3 w-[60%] rounded bg-muted/60 animate-pulse [animation-delay:400ms]" />
		</div>
	);
}

function ReportGeneratingState({ topic }: { topic: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{topic}</p>
				<TextShimmerLoader text="Putting things together" size="sm" />
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3 pb-4">
				<ContentSkeleton />
			</div>
		</div>
	);
}

function ReportErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Report Generation Failed</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				{title && title !== "Report" && (
					<p className="text-sm font-medium text-foreground line-clamp-2">{title}</p>
				)}
				<p className={`text-sm text-muted-foreground${title && title !== "Report" ? " mt-1" : ""}`}>
					{error}
				</p>
			</div>
		</div>
	);
}

function ReportCancelledState() {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-muted-foreground">Report Cancelled</p>
				<p className="text-xs text-muted-foreground mt-0.5">Report generation was cancelled</p>
			</div>
		</div>
	);
}

function ReportCard({
	reportId,
	title,
	wordCount,
	shareToken,
	autoOpen = false,
}: {
	reportId: number;
	title: string;
	wordCount?: number;
	shareToken?: string | null;
	autoOpen?: boolean;
}) {
	const openPanel = useSetAtom(openReportPanelAtom);
	const panelState = useAtomValue(reportPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 768px)");
	const autoOpenedRef = useRef(false);
	const [metadata, setMetadata] = useState<{
		title: string;
		wordCount: number | null;
		versionLabel: string | null;
		content: string | null;
	}>({ title, wordCount: wordCount ?? null, versionLabel: null, content: null });
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let cancelled = false;
		const fetchData = async () => {
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
					if (parsed.data.report_metadata?.status === "failed") {
						setError(parsed.data.report_metadata?.error_message || "Report generation failed");
					} else {
						let versionLabel: string | null = null;
						const versions = parsed.data.versions;
						if (versions && versions.length > 1) {
							const idx = versions.findIndex((v) => v.id === reportId);
							if (idx >= 0) {
								versionLabel = `version ${idx + 1}`;
							}
						}
						const resolvedTitle = parsed.data.title || title;
						const resolvedWordCount = parsed.data.report_metadata?.word_count ?? wordCount ?? null;
						setMetadata({
							title: resolvedTitle,
							wordCount: resolvedWordCount,
							versionLabel,
							content: parsed.data.content ?? null,
						});

						if (autoOpen && isDesktop && !autoOpenedRef.current) {
							autoOpenedRef.current = true;
							openPanel({
								reportId,
								title: resolvedTitle,
								wordCount: resolvedWordCount ?? undefined,
								shareToken,
							});
						}
					}
				}
			} catch {
				if (!cancelled) setError("No report found");
			} finally {
				if (!cancelled) setIsLoading(false);
			}
		};
		fetchData();
		return () => {
			cancelled = true;
		};
	}, [reportId, title, wordCount, shareToken, autoOpen, isDesktop, openPanel]);

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
			className={`my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300 ${isActive ? "ring-1 ring-primary/50" : ""}`}
		>
			<button
				type="button"
				onClick={handleOpen}
				className="w-full text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:outline-none cursor-pointer"
			>
				<div className="px-5 pt-5 pb-4 select-none">
					<p className="text-sm font-semibold text-foreground line-clamp-2">
						{isLoading ? title : metadata.title}
					</p>
					<p className="text-xs text-muted-foreground mt-0.5">
						{isLoading ? (
							<span className="inline-block h-3 w-24 rounded bg-muted/60 animate-pulse" />
						) : (
							<>
								{metadata.wordCount != null && `${metadata.wordCount.toLocaleString()} words`}
								{metadata.wordCount != null && metadata.versionLabel && (
									<Dot className="inline size-4" />
								)}
								{metadata.versionLabel}
							</>
						)}
					</p>
				</div>

				<div className="mx-5 h-px bg-border/50" />

				<div className="px-5 pt-3 pb-4">
					{isLoading ? (
						<ContentSkeleton />
					) : metadata.content ? (
						<div
							className="max-h-[7rem] overflow-hidden [&_*]:!text-[24px]"
							style={{
								maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
								WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							}}
						>
							<PlateEditor
								markdown={metadata.content}
								readOnly
								preset="readonly"
								editorVariant="none"
								className="h-auto [&_[data-slate-editor]]:!min-h-0 [&_[data-slate-editor]>*:first-child]:!mt-0"
							/>
						</div>
					) : (
						<p className="text-sm text-muted-foreground italic">No content available</p>
					)}
				</div>
			</button>
		</div>
	);
}

/**
 * Generate Report Tool UI — renders custom UI inline in chat
 * when the generate_report tool is called by the agent.
 */
export const GenerateReportToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<GenerateReportArgs, GenerateReportResult>) => {
	const params = useParams();
	const pathname = usePathname();
	const isPublicRoute = pathname?.startsWith("/public/");
	const shareToken = isPublicRoute && typeof params?.token === "string" ? params.token : null;

	const topic = args.topic || "Report";

	const sawRunningRef = useRef(false);
	if (status.type === "running" || status.type === "requires-action") {
		sawRunningRef.current = true;
	}

	if (status.type === "running" || status.type === "requires-action") {
		return <ReportGeneratingState topic={topic} />;
	}

	if (status.type === "incomplete") {
		if (status.reason === "cancelled") {
			return <ReportCancelledState />;
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

	if (!result) {
		return <ReportGeneratingState topic={topic} />;
	}

	if (result.status === "failed") {
		return (
			<ReportErrorState title={result.title || topic} error={result.error || "Generation failed"} />
		);
	}

	if (result.status === "ready" && result.report_id) {
		return (
			<ReportCard
				reportId={result.report_id}
				title={result.title || topic}
				wordCount={result.word_count ?? undefined}
				shareToken={shareToken}
				autoOpen={sawRunningRef.current}
			/>
		);
	}

	return <ReportErrorState title={topic} error="Missing report ID" />;
};
