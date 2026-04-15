"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import { useParams, usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { z } from "zod";
import { openReportPanelAtom, reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Spinner } from "@/components/ui/spinner";
import { useMediaQuery } from "@/hooks/use-media-query";
import { getAuthHeaders } from "@/lib/auth-utils";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
	"pdfjs-dist/build/pdf.worker.min.mjs",
	import.meta.url
).toString();

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
				<TextShimmerLoader text="Crafting your resume" size="sm" />
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
	const [pdfUrl, setPdfUrl] = useState<string | null>(null);
	const [pdfReady, setPdfReady] = useState(false);
	const [pdfError, setPdfError] = useState(false);
	const documentOptionsRef = useRef({ httpHeaders: getAuthHeaders() });

	useEffect(() => {
		setPdfUrl(
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

	const onPdfLoadSuccess = useCallback(() => {
		setPdfReady(true);
	}, []);

	const onPdfLoadError = useCallback(() => {
		setPdfReady(true);
		setPdfError(true);
	}, []);

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
			<button
				type="button"
				onClick={handleOpen}
				className="w-full text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:outline-none cursor-pointer select-none"
			>
				<div className="px-5 pt-5 pb-4">
					<p className="text-base font-semibold text-foreground line-clamp-2">{title}</p>
					<p className="text-sm text-muted-foreground mt-0.5">PDF</p>
				</div>

				<div className="mx-5 h-px bg-border/50" />

				<div className="px-5 pt-3 pb-4">
				{pdfUrl && !pdfError ? (
					<div
						className="max-h-[7rem] overflow-hidden pointer-events-none mix-blend-multiply dark:mix-blend-screen"
						style={{
							maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
							WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
						}}
					>
						<div className="dark:invert dark:hue-rotate-180">
							<Document
								file={pdfUrl}
								options={documentOptionsRef.current}
								onLoadSuccess={onPdfLoadSuccess}
								onLoadError={onPdfLoadError}
								loading={
									<div className="flex items-center justify-center h-[7rem]">
										<Spinner size="md" />
									</div>
								}
							>
								{pdfReady && (
									<Page
										pageNumber={1}
										renderTextLayer={false}
										renderAnnotationLayer={false}
										className="[&_canvas]:!w-full [&_canvas]:!h-auto"
									/>
								)}
							</Document>
						</div>
					</div>
					) : pdfError ? (
						<p className="text-sm text-muted-foreground italic">Preview unavailable</p>
					) : (
						<div className="flex items-center justify-center h-[7rem]">
							<Spinner size="md" />
						</div>
					)}
				</div>
			</button>
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
