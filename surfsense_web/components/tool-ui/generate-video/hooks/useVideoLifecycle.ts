"use client";

import type { PlayerRef } from "@remotion/player";
import {
	type ComponentType,
	type RefObject,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import { compileCode } from "@/app/remotion/compiler";
import { extractDuration, fetchCode, updateCode } from "../api";
import { DEFAULT_DURATION, type GenerateVideoResult, MAX_ATTEMPTS, type Phase } from "../types";

export interface VideoLifecycleState {
	phase: Phase;
	attempt: number;
	component: ComponentType | null;
	durationInFrames: number;
	finalError: string | null;
	runtimeWarning: string | null;
	generationId: number;
	playerRef: RefObject<PlayerRef | null>;
}

// Stable snapshot of what the generation loop needs. A single state value avoids
// the loop re-running when the parent re-renders with a new `result` object reference.
type GenerationTrigger = {
	result: GenerateVideoResult;
	startAttempt: number;
	lastError?: string;
} | null;

export function useVideoLifecycle(
	result: GenerateVideoResult | null,
	toolCallId: string,
	messageId: number | null,
): VideoLifecycleState {
	const [phase, setPhase] = useState<Phase>("idle");
	const [attempt, setAttempt] = useState(0);
	const [component, setComponent] = useState<ComponentType | null>(null);
	const [durationInFrames, setDurationInFrames] = useState(DEFAULT_DURATION);
	const [finalError, setFinalError] = useState<string | null>(null);
	const [runtimeWarning, setRuntimeWarning] = useState<string | null>(null);
	const [generationId, setGenerationId] = useState(0);

	const [trigger, setTrigger] = useState<GenerationTrigger>(null);

	const playerRef = useRef<PlayerRef | null>(null);
	const attemptRef = useRef(0);
	// Kept in sync with the latest result so runtime-error retries always have
	// a result to retry with, even when the generation loop was skipped on reload.
	const resultRef = useRef<GenerateVideoResult | null>(null);

	useEffect(() => {
		if (!result || result.status !== "prompt_ready") return;
		resultRef.current = result;

		if (result.code) {
			const { Component, error } = compileCode(result.code);
			if (!error && Component) {
				setComponent(() => Component);
				setDurationInFrames(extractDuration(result.code!));
				setGenerationId((id) => id + 1);
				setPhase("success");
				return;
			}
			// Persisted code no longer compiles — fall through and regenerate.
		}

		setTrigger({ result, startAttempt: 1 });
	}, [result]);

	useEffect(() => {
		if (!trigger) return;
		const { result, startAttempt, lastError: initialError } = trigger;

		let cancelled = false;
		const controller = new AbortController();

		(async () => {
			let lastError = initialError;

			for (let i = startAttempt; i <= MAX_ATTEMPTS; i++) {
				if (cancelled) return;
				setPhase("generating");
				setAttempt(i);
				attemptRef.current = i;

				try {
					const code = await fetchCode(
						result.search_space_id,
						result.topic,
						result.source_content,
						i,
						lastError,
						controller.signal,
					);

					if (cancelled) return;

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
					setGenerationId((id) => id + 1);
					setRuntimeWarning(null);
					setPhase("success");

					if (messageId) {
						updateCode(messageId, toolCallId, code).catch((err) => {
							console.warn("[video] Failed to persist compiled code:", err);
						});
					}
					return;
				} catch (err) {
					if (cancelled) return;
					if (err instanceof Error && err.name === "AbortError") return;
					lastError = err instanceof Error ? err.message : String(err);
					if (i === MAX_ATTEMPTS) {
						setFinalError(lastError);
						setPhase("failed");
					}
				}
			}
		})();

		return () => {
			cancelled = true;
			controller.abort();
		};
	}, [trigger]);

	const onRuntimeError = useCallback((errorMessage: string) => {
		console.error("[video] Runtime error:", errorMessage);
		const nextAttempt = attemptRef.current + 1;
		if (nextAttempt > MAX_ATTEMPTS) {
			setFinalError("The video could not be rendered after multiple attempts.");
			setPhase("failed");
			return;
		}
		setRuntimeWarning("A playback issue was detected. Regenerating the video…");
		setTrigger((prev) => {
			const r = prev?.result ?? resultRef.current;
			return r ? { result: r, startAttempt: nextAttempt, lastError: errorMessage } : null;
		});
	}, []);

	useEffect(() => {
		const player = playerRef.current;
		if (!player) return;

		const handleError = (e: { detail: { error: Error } }) => {
			onRuntimeError(e.detail.error.message);
		};

		player.addEventListener("error", handleError);
		return () => player.removeEventListener("error", handleError);
	}, [component, onRuntimeError]);

	return { phase, attempt, component, durationInFrames, finalError, runtimeWarning, generationId, playerRef };
}
