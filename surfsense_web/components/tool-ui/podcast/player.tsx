"use client";

import { useParams, usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Audio } from "@/components/tool-ui/audio";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { baseApiService } from "@/lib/apis/base-api.service";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";
import { speakerLabel } from "./schema";

// Public snapshots predate the transcript.turns shape and keep their own.
const publicPodcastDetailsSchema = z.object({
	podcast_transcript: z.array(z.object({ speaker_id: z.number(), dialog: z.string() })).nullish(),
});

interface TranscriptLine {
	label: string;
	text: string;
}

export function PodcastErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-destructive">Podcast Generation Failed</p>
			</div>
			<div className="mx-5 h-px bg-border/50" />
			<div className="px-5 py-4">
				<p className="text-sm font-medium text-foreground line-clamp-2">{title}</p>
				<p className="text-sm text-muted-foreground mt-1">{error}</p>
			</div>
		</div>
	);
}

function AudioLoadingState({ title }: { title: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<div className="px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2">{title}</p>
				<TextShimmerLoader text="Loading audio" size="sm" />
			</div>
		</div>
	);
}

/**
 * Streams the rendered episode and shows its transcript. Works in two modes:
 * authenticated (lifecycle stream + detail endpoints) and public shared chat
 * (share-token snapshot endpoints), detected from the route.
 */
export function PodcastPlayer({
	podcastId,
	title,
	durationMs,
}: {
	podcastId: number;
	title: string;
	durationMs?: number;
}) {
	const params = useParams();
	const pathname = usePathname();
	const isPublicRoute = pathname?.startsWith("/public/");
	const shareToken = isPublicRoute && typeof params?.token === "string" ? params.token : null;

	const [audioSrc, setAudioSrc] = useState<string | null>(null);
	const [transcriptLines, setTranscriptLines] = useState<TranscriptLine[] | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const objectUrlRef = useRef<string | null>(null);

	useEffect(() => {
		return () => {
			if (objectUrlRef.current) {
				URL.revokeObjectURL(objectUrlRef.current);
			}
		};
	}, []);

	const loadPodcast = useCallback(async () => {
		setIsLoading(true);
		setError(null);

		try {
			if (objectUrlRef.current) {
				URL.revokeObjectURL(objectUrlRef.current);
				objectUrlRef.current = null;
			}

			const controller = new AbortController();
			const timeoutId = setTimeout(() => controller.abort(), 60000);

			try {
				let audioBlob: Blob;
				let lines: TranscriptLine[] = [];

				if (shareToken) {
					const [blob, details] = await Promise.all([
						baseApiService.getBlob(`/api/v1/public/${shareToken}/podcasts/${podcastId}/stream`),
						baseApiService.get(`/api/v1/public/${shareToken}/podcasts/${podcastId}`),
					]);
					audioBlob = blob;
					const parsed = publicPodcastDetailsSchema.safeParse(details);
					lines = (parsed.success ? (parsed.data.podcast_transcript ?? []) : []).map((entry) => ({
						label: `Speaker ${entry.speaker_id + 1}`,
						text: entry.dialog,
					}));
				} else {
					const [audioResponse, detail] = await Promise.all([
						authenticatedFetch(`${BACKEND_URL}/api/v1/podcasts/${podcastId}/stream`, {
							method: "GET",
							signal: controller.signal,
						}),
						podcastsApiService.getDetail(podcastId),
					]);

					if (!audioResponse.ok) {
						throw new Error(`Failed to load audio: ${audioResponse.status}`);
					}

					audioBlob = await audioResponse.blob();
					lines = (detail.transcript?.turns ?? []).map((turn) => ({
						label: speakerLabel(detail.spec, turn.speaker),
						text: turn.text,
					}));
				}

				const objectUrl = URL.createObjectURL(audioBlob);
				objectUrlRef.current = objectUrl;
				setAudioSrc(objectUrl);
				setTranscriptLines(lines);
			} finally {
				clearTimeout(timeoutId);
			}
		} catch (err) {
			console.error("Error loading podcast:", err);
			if (err instanceof DOMException && err.name === "AbortError") {
				setError("Request timed out. Please try again.");
			} else {
				setError(err instanceof Error ? err.message : "Failed to load podcast");
			}
		} finally {
			setIsLoading(false);
		}
	}, [podcastId, shareToken]);

	useEffect(() => {
		loadPodcast();
	}, [loadPodcast]);

	if (isLoading) {
		return <AudioLoadingState title={title} />;
	}

	if (error || !audioSrc) {
		return <PodcastErrorState title={title} error={error || "Failed to load audio"} />;
	}

	const hasTranscript = transcriptLines && transcriptLines.length > 0;

	return (
		<div className="my-4">
			<Audio
				id={`podcast-${podcastId}`}
				src={audioSrc}
				title={title}
				durationMs={durationMs}
				className={hasTranscript ? "rounded-b-none border-b-0" : undefined}
			/>
			{hasTranscript ? (
				<div className="max-w-lg overflow-hidden rounded-b-2xl border border-t-0 bg-muted/30 select-none">
					<div className="mx-5 h-px bg-border/50" />
					<Accordion type="single" collapsible className="px-5">
						<AccordionItem value="transcript" className="border-b-0">
							<AccordionTrigger className="py-3 text-xs sm:text-sm font-medium text-muted-foreground hover:text-accent-foreground hover:no-underline">
								View transcript
							</AccordionTrigger>
							<AccordionContent className="pb-0">
								<div className="space-y-2 max-h-64 sm:max-h-96 overflow-y-auto select-text">
									{transcriptLines.map((line, idx) => (
										<div key={`${idx}-${line.label}`} className="text-xs sm:text-sm">
											<span className="font-medium text-primary">{line.label}:</span>{" "}
											<span className="text-muted-foreground">{line.text}</span>
										</div>
									))}
								</div>
							</AccordionContent>
						</AccordionItem>
					</Accordion>
				</div>
			) : null}
		</div>
	);
}
