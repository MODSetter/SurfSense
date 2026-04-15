"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import { FileTextIcon } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { openReportPanelAtom, reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { useMediaQuery } from "@/hooks/use-media-query";

const GenerateResumeArgsSchema = z.object({
	user_info: z.string(),
	user_instructions: z.string().nullish(),
	parent_report_id: z.number().nullish(),
});

const GenerateResumeResultSchema = z.object({
	status: z.enum(["ready", "failed"]),
	report_id: z.number().nullish(),
	title: z.string().nullish(),
	content_type: z.string().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});

type GenerateResumeArgs = z.infer<typeof GenerateResumeArgsSchema>;
type GenerateResumeResult = z.infer<typeof GenerateResumeResultSchema>;

function ResumeGeneratingState() {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<div className="flex items-center gap-2">
					<p className="text-sm font-semibold text-foreground">Resume</p>
				</div>
				<TextShimmerLoader text="Building your resume" size="sm" />
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 pt-3 pb-4">
				<div className="h-[7rem] space-y-2">
					<div className="h-3 w-full rounded bg-muted/60 animate-pulse" />
					<div className="h-3 w-[92%] rounded bg-muted/60 animate-pulse [animation-delay:100ms]" />
					<div className="h-3 w-[75%] rounded bg-muted/60 animate-pulse [animation-delay:200ms]" />
					<div className="h-3 w-[85%] rounded bg-muted/60 animate-pulse [animation-delay:300ms]" />
					<div className="h-3 w-[60%] rounded bg-muted/60 animate-pulse [animation-delay:400ms]" />
				</div>
			</div>
		</div>
	);
}

function ResumeErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<div className="flex items-center gap-2">
					<FileTextIcon className="size-4 text-destructive" />
					<p className="text-sm font-semibold text-destructive">Resume Generation Failed</p>
				</div>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm font-medium text-foreground line-clamp-2">{title}</p>
				<p className="text-sm text-muted-foreground mt-1">{error}</p>
			</div>
		</div>
	);
}

function ResumeCancelledState() {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<div className="flex items-center gap-2">
					<FileTextIcon className="size-4 text-muted-foreground" />
					<p className="text-sm font-semibold text-muted-foreground">Resume Cancelled</p>
				</div>
				<p className="text-xs text-muted-foreground mt-0.5">Resume generation was cancelled</p>
			</div>
		</div>
	);
}

function ResumeCard({
	reportId,
	title,
	shareToken,
	autoOpen = false,
}: {
	reportId: number;
	title: string;
	shareToken?: string | null;
	autoOpen?: boolean;
}) {
	const openPanel = useSetAtom(openReportPanelAtom);
	const panelState = useAtomValue(reportPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 768px)");
	const autoOpenedRef = useRef(false);
	const [pdfThumbnailUrl, setPdfThumbnailUrl] = useState<string | null>(null);

	useEffect(() => {
		setPdfThumbnailUrl(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/reports/${reportId}/preview`
		);

		if (autoOpen && isDesktop && !autoOpenedRef.current) {
			autoOpenedRef.current = true;
			openPanel({
				reportId,
				title,
				shareToken,
				contentType: "typst",
			});
		}
	}, [reportId, title, shareToken, autoOpen, isDesktop, openPanel]);

	const isActive = panelState.isOpen && panelState.reportId === reportId;

	const handleOpen = () => {
		openPanel({
			reportId,
			title,
			shareToken,
			contentType: "typst",
		});
	};

	return (
		<div
			className={`my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 transition-[box-shadow] duration-300 ${isActive ? "ring-1 ring-primary/50" : ""}`}
		>
			{/* biome-ignore lint/a11y/useSemanticElements: nested interactive content */}
			<div
				role="button"
				tabIndex={0}
				onClick={handleOpen}
				onKeyDown={(e) => {
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault();
						handleOpen();
					}
				}}
				className="w-full text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:outline-none cursor-pointer"
			>
				<div className="px-5 pt-5 pb-4 select-none">
					<div className="flex items-center gap-2">
						<FileTextIcon className="size-4 text-primary" />
						<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
					</div>
					<p className="text-xs text-muted-foreground mt-0.5">Resume • Click to preview</p>
				</div>

				<div className="mx-5 h-px bg-border/50" />

				<div className="px-5 pt-3 pb-4 flex items-center justify-center">
					{pdfThumbnailUrl ? (
						<div className="flex items-center gap-3 text-muted-foreground">
							<FileTextIcon className="size-8 text-primary/40" />
							<span className="text-sm">PDF Resume ready — click to view</span>
						</div>
					) : (
						<div className="h-[7rem] space-y-2 w-full">
							<div className="h-3 w-full rounded bg-muted/60 animate-pulse" />
							<div className="h-3 w-[92%] rounded bg-muted/60 animate-pulse [animation-delay:100ms]" />
							<div className="h-3 w-[75%] rounded bg-muted/60 animate-pulse [animation-delay:200ms]" />
						</div>
					)}
				</div>
			</div>
		</div>
	);
}

export const GenerateResumeToolUI = ({
	result,
	status,
}: ToolCallMessagePartProps<GenerateResumeArgs, GenerateResumeResult>) => {
	const params = useParams();
	const pathname = usePathname();
	const isPublicRoute = pathname?.startsWith("/public/");
	const shareToken = isPublicRoute && typeof params?.token === "string" ? params.token : null;

	const sawRunningRef = useRef(false);
	if (status.type === "running" || status.type === "requires-action") {
		sawRunningRef.current = true;
	}

	if (status.type === "running" || status.type === "requires-action") {
		return <ResumeGeneratingState />;
	}

	if (status.type === "incomplete") {
		if (status.reason === "cancelled") {
			return <ResumeCancelledState />;
		}
		if (status.reason === "error") {
			return (
				<ResumeErrorState
					title="Resume"
					error={typeof status.error === "string" ? status.error : "An error occurred"}
				/>
			);
		}
	}

	if (!result) {
		return <ResumeGeneratingState />;
	}

	if (result.status === "failed") {
		return (
			<ResumeErrorState
				title={result.title || "Resume"}
				error={result.error || "Resume generation failed. Please try again or rephrase your request."}
			/>
		);
	}

	if (result.status === "ready" && result.report_id) {
		return (
			<ResumeCard
				reportId={result.report_id}
				title={result.title || "Resume"}
				shareToken={shareToken}
				autoOpen={sawRunningRef.current}
			/>
		);
	}

	return <ResumeErrorState title="Resume" error="Missing report ID" />;
};
