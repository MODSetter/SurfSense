"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { Dot, Download, Loader2, Presentation, X } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { baseApiService } from "@/lib/apis/base-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { compileCheck, compileToComponent } from "@/lib/remotion/compile-check";
import { FPS } from "@/lib/remotion/constants";
import {
	buildCompositionComponent,
	buildSlideWithWatermark,
	CombinedPlayer,
	type CompiledSlide,
} from "./combined-player";
import { getPptxExportErrorToast, getVideoDownloadErrorToast } from "./errors";

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
			})
		)
		.nullish(),
	scene_codes: z
		.array(
			z.object({
				slide_number: z.number(),
				code: z.string(),
				title: z.string().nullish(),
			})
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
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<TextShimmerLoader text="Generating video presentation" size="sm" />
			</div>
		</div>
	);
}

function ErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Video Generation Failed</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm font-medium text-foreground line-clamp-2">{title}</p>
				<p className="text-sm text-muted-foreground mt-1">{error}</p>
			</div>
		</div>
	);
}

function CompilationLoadingState({ title }: { title: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<TextShimmerLoader text="Compiling scenes" size="sm" />
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
					console.warn(`Slide ${slide.slide_number} failed to compile: ${check.error}`);
					continue;
				}

				const component = compileToComponent(scene.code, durationInFrames);

				compiled.push({
					component,
					title: scene.title ?? slide.title,
					code: scene.code,
					durationInFrames,
					audioUrl: slide.audio_url ? `${backendUrl}${slide.audio_url}` : undefined,
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
							blob = await baseApiService.getBlob(new URL(slide.audioUrl).pathname);
						} else {
							const resp = await authenticatedFetch(slide.audioUrl, {
								method: "GET",
							});
							if (!resp.ok) {
								console.warn(`Audio fetch ${resp.status} for slide "${slide.title}"`);
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
				})
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
		[compiledSlides]
	);

	const handleDownload = async () => {
		if (isRendering || compiledSlides.length === 0) return;

		setIsRendering(true);
		setRenderProgress(0);
		setRenderFormat(null);

		const controller = new AbortController();
		abortControllerRef.current = controller;

		try {
			const { canRenderMediaOnWeb, renderMediaOnWeb } = await import("@remotion/web-renderer");

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
					"Your browser does not support video rendering (WebCodecs). Please use Chrome, Edge, or Firefox 130+."
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
			if ((err as Error).name !== "AbortError") {
				const { title, description } = getVideoDownloadErrorToast(err);
				toast.error(title, { description });
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
						})
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

			for (const r of roots) r.unmount();
			document.body.removeChild(offscreen);
		} catch (err) {
			const { title, description } = getPptxExportErrorToast(err);
			toast.error(title, { description });
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
		<div className="my-4 max-w-2xl overflow-hidden rounded-2xl border bg-muted/30 select-none">
			{/* Header */}
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<p className="text-xs text-muted-foreground mt-0.5 flex items-center">
					{compiledSlides.length} slides <Dot className="size-4" /> {totalDuration.toFixed(1)}s{" "}
					<Dot className="size-4" /> {FPS}fps
				</p>
			</div>

			<div className="mx-5 h-px bg-border/50" />

			{/* Remotion Player */}
			<div className="px-5 pt-3">
				<CombinedPlayer slides={compiledSlides} />
			</div>

			<div className="mx-5 mt-3 h-px bg-border/50" />

			{/* Action buttons */}
			<div className="px-5 py-3 flex items-center gap-2 flex-wrap">
				{isRendering ? (
					<>
						<div className="flex items-center gap-2">
							<Loader2 className="size-3.5 animate-spin text-muted-foreground" />
							<span className="text-xs font-medium text-muted-foreground">
								Rendering {renderFormat ?? ""}{" "}
								{renderProgress !== null ? `${Math.round(renderProgress * 100)}%` : "..."}
							</span>
							<div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
								<div
									className="h-full rounded-full bg-muted-foreground/60 transition-[box-shadow] duration-300"
									style={{ width: `${(renderProgress ?? 0) * 100}%` }}
								/>
							</div>
						</div>
						<Button
							variant="ghost"
							size="icon"
							onClick={handleCancelRender}
							className="size-7 text-muted-foreground"
						>
							<X className="size-3.5" />
						</Button>
					</>
				) : (
					<>
						<Button
							variant="ghost"
							size="sm"
							onClick={handleDownload}
							className="gap-1.5 h-7 px-2.5 text-xs text-muted-foreground"
						>
							<Download className="size-3.5" />
							Download MP4
						</Button>
						<Button
							variant="ghost"
							size="sm"
							onClick={handleDownloadPPTX}
							disabled={isPptxExporting}
							className="gap-1.5 h-7 px-2.5 text-xs text-muted-foreground"
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
						</Button>
					</>
				)}
			</div>
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

export const GenerateVideoPresentationToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<GenerateVideoPresentationArgs, GenerateVideoPresentationResult>) => {
	const params = useParams();
	const pathname = usePathname();
	const isPublicRoute = pathname?.startsWith("/public/");
	const shareToken = isPublicRoute && typeof params?.token === "string" ? params.token : null;

	const title = args.video_title || "SurfSense Presentation";

	if (status.type === "running" || status.type === "requires-action") {
		return <GeneratingState title={title} />;
	}

	if (status.type === "incomplete") {
		if (status.reason === "cancelled") {
			return (
				<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
					<div className="px-5 pt-5 pb-4">
						<p className="text-sm font-semibold text-muted-foreground">Presentation Cancelled</p>
						<p className="text-xs text-muted-foreground mt-0.5">
							Presentation generation was cancelled
						</p>
					</div>
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
			<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
				<div className="px-5 pt-5 pb-4">
					<p className="text-sm font-semibold text-foreground">Presentation already in progress</p>
					<p className="text-xs text-muted-foreground mt-0.5">
						Please wait for the current presentation to complete.
					</p>
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
};
