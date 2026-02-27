"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { type ErrorFallback, Player } from "@remotion/player";
import { VideoIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { compileCode } from "@/app/remotion/compiler";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { getBearerToken } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_ATTEMPTS = 3;
const MIN_DURATION = 900;
const MAX_DURATION = 9000;
const DEFAULT_DURATION = 1800;

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const GenerateVideoArgsSchema = z.object({
	topic: z.string(),
	source_content: z.string(),
});

const GenerateVideoResultSchema = z.object({
	status: z.literal("prompt_ready"),
	search_space_id: z.number(),
	topic: z.string(),
	source_content: z.string(),
});

type GenerateVideoArgs = z.infer<typeof GenerateVideoArgsSchema>;
type GenerateVideoResult = z.infer<typeof GenerateVideoResultSchema>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractDuration(code: string): number {
	const match = code.match(/\bTOTAL_DURATION\s*=\s*(\d+)/);
	if (!match) return DEFAULT_DURATION;
	const n = parseInt(match[1], 10);
	return Math.min(MAX_DURATION, Math.max(MIN_DURATION, n));
}

async function fetchCode(
	searchSpaceId: number,
	topic: string,
	sourceContent: string,
	attempt: number,
	error?: string
): Promise<string> {
	const token = getBearerToken();
	const res = await fetch(`${BACKEND_URL}/api/v1/video/generate-code`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token || ""}`,
		},
		body: JSON.stringify({
			search_space_id: searchSpaceId,
			topic,
			source_content: sourceContent,
			attempt,
			error: error ?? null,
		}),
	});

	if (!res.ok) {
		const detail = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(detail.detail || `HTTP ${res.status}`);
	}

	const data = await res.json();
	return data.code as string;
}

// ---------------------------------------------------------------------------
// Remotion runtime error fallback
// ---------------------------------------------------------------------------

const runtimeErrorFallback: ErrorFallback = ({ error }) => (
	<div
		style={{
			backgroundColor: "#0a0a0f",
			display: "flex",
			flexDirection: "column",
			alignItems: "center",
			justifyContent: "center",
			width: "100%",
			aspectRatio: "16/9",
			gap: 8,
			color: "#ff6b6b",
			fontFamily: "monospace",
			fontSize: 13,
			padding: 24,
			wordBreak: "break-word",
			textAlign: "center",
		}}
	>
		<span style={{ fontSize: 15, fontWeight: 600 }}>Runtime error</span>
		<span>{error.message}</span>
	</div>
);

// ---------------------------------------------------------------------------
// UI states
// ---------------------------------------------------------------------------

function VideoLoadingState({ topic, attempt }: { topic: string; attempt: number }) {
	const label =
		attempt <= 1
			? "Composing visual content"
			: `Retrying animation (attempt ${attempt}/${MAX_ATTEMPTS})`;

	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex w-full items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
					<VideoIcon className="size-4 sm:size-6 text-primary" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{topic}
					</h3>
					<TextShimmerLoader text={label} size="sm" />
				</div>
			</div>
		</div>
	);
}

function VideoErrorState({ title, error }: { title: string; error: string }) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-muted/60">
					<VideoIcon className="size-4 sm:size-6 text-muted-foreground" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-muted-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{title}
					</h3>
					<p className="text-muted-foreground/60 text-[11px] sm:text-xs mt-0.5 line-clamp-2">
						{error}
					</p>
				</div>
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Tool UI
// ---------------------------------------------------------------------------

type Phase = "idle" | "generating" | "success" | "failed";

export const GenerateVideoToolUI = makeAssistantToolUI<GenerateVideoArgs, GenerateVideoResult>({
	toolName: "generate_video",
	render: function GenerateVideoUI({ args, result, status }) {
		const topic = args.topic || "Video";

		const [phase, setPhase] = useState<Phase>("idle");
		const [attempt, setAttempt] = useState(0);
		const [component, setComponent] = useState<React.ComponentType | null>(null);
		const [durationInFrames, setDurationInFrames] = useState(DEFAULT_DURATION);
		const [finalError, setFinalError] = useState<string | null>(null);
		const hasStarted = useRef(false);

		useEffect(() => {
			if (!result || result.status !== "prompt_ready") return;
			if (hasStarted.current) return;
			hasStarted.current = true;

			(async () => {
				let lastError: string | undefined;

				for (let i = 1; i <= MAX_ATTEMPTS; i++) {
					setPhase("generating");
					setAttempt(i);

					try {
						const code = await fetchCode(
							result.search_space_id,
							result.topic,
							result.source_content,
							i,
							lastError
						);

						const { Component, error: compileError } = compileCode(code);

						if (compileError) {
							lastError = compileError;
							if (i === MAX_ATTEMPTS) {
								setFinalError(compileError);
								setPhase("failed");
							}
							continue;
						}

						setComponent(() => Component);
						setDurationInFrames(extractDuration(code));
						setPhase("success");
						return;
					} catch (err) {
						lastError = err instanceof Error ? err.message : String(err);
						if (i === MAX_ATTEMPTS) {
							setFinalError(lastError);
							setPhase("failed");
						}
					}
				}
			})();
		}, [result]);

		// Tool still running (LLM agent thinking / calling the tool)
		if (status.type === "running" || status.type === "requires-action") {
			return <VideoLoadingState topic={topic} attempt={0} />;
		}

		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return (
					<div className="my-4 rounded-xl border border-muted p-3 sm:p-4 text-muted-foreground">
						<p className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
							<VideoIcon className="size-3.5 sm:size-4" />
							<span className="line-through">Video generation cancelled</span>
						</p>
					</div>
				);
			}
			const errMsg = typeof status.error === "string" ? status.error : "An error occurred";
			return <VideoErrorState title={topic} error={errMsg} />;
		}

		// result received — frontend generation lifecycle
		if (phase === "idle" || phase === "generating") {
			return <VideoLoadingState topic={topic} attempt={attempt} />;
		}

		if (phase === "failed") {
			return (
				<VideoErrorState title={topic} error={finalError || "Generation failed after 3 attempts"} />
			);
		}

		if (phase === "success" && component) {
			return (
				<div className="my-4">
					<Player
						component={component}
						durationInFrames={durationInFrames}
						fps={30}
						compositionWidth={1920}
						compositionHeight={1080}
						style={{ width: "100%", borderRadius: 8 }}
						errorFallback={runtimeErrorFallback}
						controls
						autoPlay
						loop
					/>
				</div>
			);
		}

		return <VideoErrorState title={topic} error="Missing video component" />;
	},
});
