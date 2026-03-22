"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertCircleIcon,
	Download,
	Film,
	Loader2,
	Presentation,
	X,
} from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { z } from "zod";
import { Spinner } from "@/components/ui/spinner";
import { baseApiService } from "@/lib/apis/base-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { compileCheck, compileToComponent } from "@/lib/remotion/compile-check";
import { FPS } from "@/lib/remotion/constants";
import {
	CombinedPlayer,
	buildCompositionComponent,
	buildSlideWithWatermark,
	type CompiledSlide,
} from "./combined-player";

const GenerateVideoPresentationArgsSchema = z.object({
	source_content: z.string(),
	video_title: z.string().nullish(),
	user_prompt: z.string().nullish(),
});

const GenerateVideoPresentationResultSchema = z.object({
	status: z.enum(["pending", "generating", "ready", "failed"]),
	video_presentation_id: z.number().nullish(),
	title: z.string().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});

const VideoPresentationStatusResponseSchema = z.object({
	status: z.enum(["pending", "generating", "ready", "failed"]),
	id: z.number(),
	title: z.string(),
	slides: z
		.array(
			z.object({
				slide_number: z.number(),
				title: z.string(),
				subtitle: z.string().nullish(),
				content_in_markdown: z.string().nullish(),
				speaker_transcripts: z.array(z.string()).nullish(),
				background_explanation: z.string().nullish(),
				audio_url: z.string().nullish(),
				duration_seconds: z.number().nullish(),
				duration_in_frames: z.number().nullish(),
			}),
		)
		.nullish(),
	scene_codes: z
		.array(
			z.object({
				slide_number: z.number(),
				code: z.string(),
				title: z.string().nullish(),
			}),
		)
		.nullish(),
	slide_count: z.number().nullish(),
});

type GenerateVideoPresentationArgs = z.infer<typeof GenerateVideoPresentationArgsSchema>;
type GenerateVideoPresentationResult = z.infer<typeof GenerateVideoPresentationResultSchema>;
type VideoPresentationStatusResponse = z.infer<typeof VideoPresentationStatusResponseSchema>;

function parseStatusResponse(data: unknown): VideoPresentationStatusResponse | null {
	const result = VideoPresentationStatusResponseSchema.safeParse(data);
	if (!result.success) {
		console.warn("Invalid video presentation status:", result.error.issues);
		return null;
	}
	return result.data;
}

function GeneratingState({ title }: { title: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-primary/20 bg-linear-to-br from-primary/5 to-primary/10 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="relative shrink-0">
					<div className="flex size-12 sm:size-16 items-center justify-center rounded-full bg-primary/20">
						<Film className="size-6 sm:size-8 text-primary" />
					</div>
					<div className="absolute inset-1 animate-ping rounded-full bg-primary/20" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-lg leading-tight">
						{title}
					</h3>
					<div className="mt-1.5 sm:mt-2 flex items-center gap-1.5 sm:gap-2 text-muted-foreground">
						<Spinner size="sm" className="size-3 sm:size-4" />
						<span className="text-xs sm:text-sm">
							Generating video presentation. This may take a few minutes.
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

function ErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="flex size-12 sm:size-16 shrink-0 items-center justify-center rounded-full bg-destructive/10">
					<AlertCircleIcon className="size-6 sm:size-8 text-destructive" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight">
						{title}
					</h3>
					<p className="mt-1 text-destructive text-xs sm:text-sm">
						Failed to generate video presentation
					</p>
					<p className="mt-1.5 sm:mt-2 text-muted-foreground text-xs sm:text-sm">{error}</p>
				</div>
			</div>
		</div>
	);
}

function CompilationLoadingState({ title }: { title: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-muted/30 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="flex size-12 sm:size-16 shrink-0 items-center justify-center rounded-full bg-primary/10">
					<Film className="size-6 sm:size-8 text-primary/50" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight">
						{title}
					</h3>
					<div className="mt-1.5 sm:mt-2 flex items-center gap-1.5 sm:gap-2 text-muted-foreground">
						<Spinner size="sm" className="size-3 sm:size-4" />
						<span className="text-xs sm:text-sm">Compiling scenes...</span>
					</div>
				</div>
			</div>
		</div>
	);
}

function VideoPresentationPlayer({
	presentationId,
	title,
	shareToken,
}: {
	presentationId: number;
	title: string;
	shareToken?: string | null;
}) {
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [compiledSlides, setCompiledSlides] = useState<CompiledSlide[]>([]);

	const [isRendering, setIsRendering] = useState(false);
	const [renderProgress, setRenderProgress] = useState<number | null>(null);
	const [renderError, setRenderError] = useState<string | null>(null);
	const [renderFormat, setRenderFormat] = useState<string | null>(null);
	const abortControllerRef = useRef<AbortController | null>(null);

	const [isPptxExporting, setIsPptxExporting] = useState(false);
	const [pptxProgress, setPptxProgress] = useState<string | null>(null);

	const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ?? "";
	const audioBlobUrlsRef = useRef<string[]>([]);

	const loadPresentation = useCallback(async () => {
		setIsLoading(true);
		setError(null);
		try {
			const apiPath = shareToken
				? `/api/v1/public/${shareToken}/video-presentations/${presentationId}`
				: `/api/v1/video-presentations/${presentationId}`;

			const raw = await baseApiService.get<unknown>(apiPath);
			const data = parseStatusResponse(raw);
			if (!data) throw new Error("Invalid response");
			if (data.status !== "ready") throw new Error(`Unexpected status: ${data.status}`);
			if (!data.slides?.length || !data.scene_codes?.length) {
				throw new Error("No slides or scene codes in response");
			}

			const sceneMap = new Map(data.scene_codes.map((sc) => [sc.slide_number, sc]));

			const compiled: CompiledSlide[] = [];
			for (const slide of data.slides) {
				const scene = sceneMap.get(slide.slide_number);
				if (!scene) continue;

				const durationInFrames = slide.duration_in_frames ?? 300;
				const check = compileCheck(scene.code);
				if (!check.success) {
					console.warn(
						`Slide ${slide.slide_number} failed to compile: ${check.error}`,
					);
					continue;
				}

				const component = compileToComponent(scene.code, durationInFrames);

				compiled.push({
					component,
					title: scene.title ?? slide.title,
					code: scene.code,
					durationInFrames,
					audioUrl: slide.audio_url
						? `${backendUrl}${slide.audio_url}`
						: undefined,
				});
			}

			if (compiled.length === 0) {
				throw new Error("No slides compiled successfully");
			}

			// Pre-fetch audio and convert to blob URLs.
			// For public routes the audio endpoints don't need auth, but we
			// still use blob URLs so Remotion's plain <audio> element works.
			const withBlobs = await Promise.all(
				compiled.map(async (slide) => {
					if (!slide.audioUrl) return slide;
					try {
						let blob: Blob;
						if (shareToken) {
							blob = await baseApiService.getBlob(
								new URL(slide.audioUrl).pathname,
							);
						} else {
							const resp = await authenticatedFetch(slide.audioUrl, {
								method: "GET",
							});
							if (!resp.ok) {
								console.warn(
									`Audio fetch ${resp.status} for slide "${slide.title}"`,
								);
								return { ...slide, audioUrl: undefined };
							}
							blob = await resp.blob();
						}
						const blobUrl = URL.createObjectURL(blob);
						audioBlobUrlsRef.current.push(blobUrl);
						return { ...slide, audioUrl: blobUrl };
					} catch (err) {
						console.warn(`Failed to fetch audio for "${slide.title}":`, err);
						return { ...slide, audioUrl: undefined };
					}
				}),
			);

			setCompiledSlides(withBlobs);
		} catch (err) {
			console.error("Error loading video presentation:", err);
			setError(err instanceof Error ? err.message : "Failed to load presentation");
		} finally {
			setIsLoading(false);
		}
	}, [presentationId, backendUrl, shareToken]);

	useEffect(() => {
		loadPresentation();
		return () => {
			for (const url of audioBlobUrlsRef.current) {
				URL.revokeObjectURL(url);
			}
			audioBlobUrlsRef.current = [];
		};
	}, [loadPresentation]);

	const totalDuration = useMemo(
		() => compiledSlides.reduce((sum, s) => sum + s.durationInFrames / FPS, 0),
		[compiledSlides],
	);

	const handleDownload = async () => {
		if (isRendering || compiledSlides.length === 0) return;

		setIsRendering(true);
		setRenderProgress(0);
		setRenderError(null);
		setRenderFormat(null);

		const controller = new AbortController();
		abortControllerRef.current = controller;

		try {
			const { canRenderMediaOnWeb, renderMediaOnWeb } = await import(
				"@remotion/web-renderer"
			);

			const formats = [
				{ container: "mp4" as const, videoCodec: "h264" as const, ext: "mp4" },
				{ container: "mp4" as const, videoCodec: "h265" as const, ext: "mp4" },
				{ container: "webm" as const, videoCodec: "vp8" as const, ext: "webm" },
				{ container: "webm" as const, videoCodec: "vp9" as const, ext: "webm" },
			];

			let chosen: (typeof formats)[number] | null = null;
			for (const fmt of formats) {
				const { canRender } = await canRenderMediaOnWeb({
					width: 1920,
					height: 1080,
					container: fmt.container,
					videoCodec: fmt.videoCodec,
				});
				if (canRender) {
					chosen = fmt;
					break;
				}
			}

			if (!chosen) {
				throw new Error(
					"Your browser does not support video rendering (WebCodecs). Please use Chrome, Edge, or Firefox 130+.",
				);
			}

			setRenderFormat(chosen.ext.toUpperCase());

			const totalFrames = compiledSlides.reduce((sum, s) => sum + s.durationInFrames, 0);
			const CompositionComponent = buildCompositionComponent(compiledSlides);

			const { getBlob } = await renderMediaOnWeb({
				composition: {
					component: CompositionComponent,
					durationInFrames: totalFrames,
					fps: FPS,
					width: 1920,
					height: 1080,
					id: "combined-video",
				},
				container: chosen.container,
				videoCodec: chosen.videoCodec,
				videoBitrate: "high",
				onProgress: ({ progress }) => {
					setRenderProgress(progress);
				},
				signal: controller.signal,
			});

			const blob = await getBlob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = `video.${chosen.ext}`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (err) {
			if ((err as Error).name === "AbortError") {
				// User cancelled
			} else {
				setRenderError(err instanceof Error ? err.message : "Failed to render video");
			}
		} finally {
			setIsRendering(false);
			setRenderProgress(null);
			abortControllerRef.current = null;
		}
	};

	const handleCancelRender = () => {
		abortControllerRef.current?.abort();
	};

	const handleDownloadPPTX = async () => {
		if (isPptxExporting || compiledSlides.length === 0) return;

		setIsPptxExporting(true);
		setPptxProgress("Preparing...");
		setRenderError(null);

		try {
			const { exportToPptx } = await import("dom-to-pptx");
			const { Thumbnail } = await import("@remotion/player");
			const { createRoot } = await import("react-dom/client");
			const { flushSync } = await import("react-dom");

			const offscreen = document.createElement("div");
			offscreen.style.cssText =
				"position:fixed;left:-99999px;top:0;overflow:hidden;pointer-events:none;";
			document.body.appendChild(offscreen);

			const slideElements: HTMLElement[] = [];
			const roots: ReturnType<typeof createRoot>[] = [];

			for (let i = 0; i < compiledSlides.length; i++) {
				const slide = compiledSlides[i];
				setPptxProgress(`Rendering slide ${i + 1}/${compiledSlides.length}...`);

				const wrapper = document.createElement("div");
				wrapper.style.cssText = "width:1920px;height:1080px;overflow:hidden;";
				offscreen.appendChild(wrapper);

				const holdFrame = Math.floor(slide.durationInFrames * 0.3);
				const root = createRoot(wrapper);
				const SlideWithWatermark = buildSlideWithWatermark(slide.component);

				flushSync(() => {
					root.render(
						React.createElement(Thumbnail, {
							component: SlideWithWatermark,
							compositionWidth: 1920,
							compositionHeight: 1080,
							frameToDisplay: holdFrame,
							durationInFrames: slide.durationInFrames,
							fps: FPS,
							style: { width: 1920, height: 1080 },
						}),
					);
				});

				await new Promise((r) => setTimeout(r, 500));
				slideElements.push(wrapper);
				roots.push(root);
			}

			setPptxProgress("Converting to editable PPTX...");

			await exportToPptx(slideElements, {
				fileName: "presentation.pptx",
			});

			roots.forEach((r) => r.unmount());
			document.body.removeChild(offscreen);
		} catch (err) {
			setRenderError(err instanceof Error ? err.message : "Failed to export PPTX");
		} finally {
			setIsPptxExporting(false);
			setPptxProgress(null);
		}
	};

	if (isLoading) {
		return <CompilationLoadingState title={title} />;
	}

	if (error || compiledSlides.length === 0) {
		return <ErrorState title={title} error={error || "Failed to compile scenes"} />;
	}

	return (
		<div className="my-4 space-y-3">
			{/* Title bar with actions */}
			<div className="flex items-center justify-between flex-wrap gap-2">
				<div className="flex items-center gap-3 min-w-0">
					<div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
						<Film className="size-4 text-primary" />
					</div>
					<div className="min-w-0">
						<h3 className="text-sm font-semibold text-foreground truncate">{title}</h3>
						<p className="text-xs text-muted-foreground">
							{compiledSlides.length} slides &middot; {totalDuration.toFixed(1)}s &middot;{" "}
							{FPS}fps
						</p>
					</div>
				</div>

				<div className="flex items-center gap-2">
					{isRendering ? (
						<>
							<div className="flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5">
								<Loader2 className="size-3.5 animate-spin text-primary" />
								<span className="text-xs font-medium">
									Rendering {renderFormat ?? ""}{" "}
									{renderProgress !== null
										? `${Math.round(renderProgress * 100)}%`
										: "..."}
								</span>
								<div className="h-1.5 w-20 overflow-hidden rounded-full bg-secondary">
									<div
										className="h-full rounded-full bg-primary transition-all duration-300"
										style={{ width: `${(renderProgress ?? 0) * 100}%` }}
									/>
								</div>
							</div>
							<button
								onClick={handleCancelRender}
								className="rounded-lg border p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
								title="Cancel render"
								type="button"
							>
								<X className="size-3.5" />
							</button>
						</>
					) : (
						<>
							<button
								onClick={handleDownload}
								className="inline-flex items-center gap-1.5 rounded-lg border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-secondary"
								type="button"
							>
								<Download className="size-3.5" />
								Download MP4
							</button>
							<button
								onClick={handleDownloadPPTX}
								disabled={isPptxExporting}
								className="inline-flex items-center gap-1.5 rounded-lg border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
								type="button"
							>
								{isPptxExporting ? (
									<>
										<Loader2 className="size-3.5 animate-spin" />
										{pptxProgress ?? "Exporting..."}
									</>
								) : (
									<>
										<Presentation className="size-3.5" />
										Download PPTX
									</>
								)}
							</button>
						</>
					)}
				</div>
			</div>

			{/* Render error */}
			{renderError && (
				<div className="flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-3">
					<AlertCircleIcon className="mt-0.5 size-4 shrink-0 text-destructive" />
					<div>
						<p className="text-sm font-medium text-destructive">Download Failed</p>
						<p className="mt-1 text-xs text-destructive/70 whitespace-pre-wrap">
							{renderError}
						</p>
					</div>
				</div>
			)}

			{/* Combined Remotion Player */}
			<CombinedPlayer slides={compiledSlides} />
		</div>
	);
}

function StatusPoller({
	presentationId,
	title,
	shareToken,
}: {
	presentationId: number;
	title: string;
	shareToken?: string | null;
}) {
	const [status, setStatus] = useState<VideoPresentationStatusResponse | null>(null);
	const pollingRef = useRef<NodeJS.Timeout | null>(null);

	useEffect(() => {
		const poll = async () => {
			try {
				const apiPath = shareToken
					? `/api/v1/public/${shareToken}/video-presentations/${presentationId}`
					: `/api/v1/video-presentations/${presentationId}`;

				const raw = await baseApiService.get<unknown>(apiPath);
				const response = parseStatusResponse(raw);
				if (response) {
					setStatus(response);
					if (response.status === "ready" || response.status === "failed") {
						if (pollingRef.current) {
							clearInterval(pollingRef.current);
							pollingRef.current = null;
						}
					}
				}
			} catch (err) {
				console.error("Error polling video presentation status:", err);
			}
		};

		poll();
		pollingRef.current = setInterval(poll, 5000);

		return () => {
			if (pollingRef.current) {
				clearInterval(pollingRef.current);
			}
		};
	}, [presentationId, shareToken]);

	if (!status || status.status === "pending" || status.status === "generating") {
		return <GeneratingState title={title} />;
	}

	if (status.status === "failed") {
		return <ErrorState title={title} error="Generation failed" />;
	}

	if (status.status === "ready") {
		return (
			<VideoPresentationPlayer
				presentationId={status.id}
				title={status.title || title}
				shareToken={shareToken}
			/>
		);
	}

	return <ErrorState title={title} error="Unexpected state" />;
}

export const GenerateVideoPresentationToolUI = makeAssistantToolUI<
	GenerateVideoPresentationArgs,
	GenerateVideoPresentationResult
>({
	toolName: "generate_video_presentation",
	render: function GenerateVideoPresentationUI({ args, result, status }) {
		const params = useParams();
		const pathname = usePathname();
		const isPublicRoute = pathname?.startsWith("/public/");
		const shareToken =
			isPublicRoute && typeof params?.token === "string" ? params.token : null;

		const title = args.video_title || "SurfSense Presentation";

		if (status.type === "running" || status.type === "requires-action") {
			return <GeneratingState title={title} />;
		}

		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return (
					<div className="my-4 rounded-xl border border-muted p-3 sm:p-4 text-muted-foreground">
						<p className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
							<Film className="size-3.5 sm:size-4" />
							<span className="line-through">Presentation generation cancelled</span>
						</p>
					</div>
				);
			}
			if (status.reason === "error") {
				return (
					<ErrorState
						title={title}
						error={typeof status.error === "string" ? status.error : "An error occurred"}
					/>
				);
			}
		}

		if (!result) {
			return <GeneratingState title={title} />;
		}

		if (result.status === "failed") {
			return <ErrorState title={title} error={result.error || "Generation failed"} />;
		}

		if (result.status === "generating") {
			return (
				<div className="my-4 overflow-hidden rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 sm:p-4">
					<div className="flex items-center gap-2.5 sm:gap-3">
						<div className="flex size-8 sm:size-10 shrink-0 items-center justify-center rounded-full bg-amber-500/20">
							<Film className="size-4 sm:size-5 text-amber-500" />
						</div>
						<div className="min-w-0">
							<p className="text-amber-600 dark:text-amber-400 text-xs sm:text-sm font-medium">
								Presentation already in progress
							</p>
							<p className="text-muted-foreground text-[10px] sm:text-xs mt-0.5">
								Please wait for the current presentation to complete.
							</p>
						</div>
					</div>
				</div>
			);
		}

		if (result.status === "pending" && result.video_presentation_id) {
			return (
				<StatusPoller
					presentationId={result.video_presentation_id}
					title={result.title || title}
					shareToken={shareToken}
				/>
			);
		}

		if (result.status === "ready" && result.video_presentation_id) {
			return (
				<VideoPresentationPlayer
					presentationId={result.video_presentation_id}
					title={result.title || title}
					shareToken={shareToken}
				/>
			);
		}

		return <ErrorState title={title} error="Missing presentation ID" />;
	},
});
