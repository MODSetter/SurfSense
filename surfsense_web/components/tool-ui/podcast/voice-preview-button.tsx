"use client";

import { Loader2, Play, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";

// Comparing voices means replaying the same samples, so each voice is fetched
// at most once per page lifetime.
const sampleUrls = new Map<string, Promise<string>>();

// Overlapping samples are useless for comparison, so only one plays at a time.
let activeAudio: HTMLAudioElement | null = null;
let stopActive: (() => void) | null = null;

function getSampleUrl(voiceId: string): Promise<string> {
	let url = sampleUrls.get(voiceId);
	if (!url) {
		url = podcastsApiService.previewVoice(voiceId).then((blob) => URL.createObjectURL(blob));
		// A failed fetch must not poison the cache for retries.
		url.catch(() => sampleUrls.delete(voiceId));
		sampleUrls.set(voiceId, url);
	}
	return url;
}

/** Plays a short sample of `voiceId` so users pick voices by sound. */
export function VoicePreviewButton({ voiceId }: { voiceId: string }) {
	const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
	const mountedRef = useRef(true);

	useEffect(() => {
		mountedRef.current = true;
		return () => {
			mountedRef.current = false;
			if (stopActive && activeAudio?.dataset.voiceId === voiceId) {
				stopActive();
			}
		};
	}, [voiceId]);

	const stop = () => {
		if (stopActive) stopActive();
	};

	const play = async () => {
		stop();
		setState("loading");
		try {
			const url = await getSampleUrl(voiceId);
			if (!mountedRef.current) return;

			const audio = new Audio(url);
			audio.dataset.voiceId = voiceId;
			activeAudio = audio;
			stopActive = () => {
				audio.pause();
				activeAudio = null;
				stopActive = null;
				if (mountedRef.current) setState("idle");
			};
			audio.onended = () => {
				if (activeAudio === audio) {
					activeAudio = null;
					stopActive = null;
				}
				if (mountedRef.current) setState("idle");
			};
			await audio.play();
			if (mountedRef.current) setState("playing");
		} catch (error) {
			if (mountedRef.current) setState("idle");
			toast.error(error instanceof Error ? error.message : "Couldn't play the voice sample");
		}
	};

	const isPlaying = state === "playing";

	return (
		<Button
			type="button"
			variant="ghost"
			size="icon"
			aria-label={isPlaying ? "Stop voice sample" : "Play voice sample"}
			disabled={state === "loading"}
			onClick={isPlaying ? stop : play}
		>
			{state === "loading" ? (
				<Loader2 className="size-4 animate-spin" />
			) : isPlaying ? (
				<Square className="size-4" />
			) : (
				<Play className="size-4" />
			)}
		</Button>
	);
}
