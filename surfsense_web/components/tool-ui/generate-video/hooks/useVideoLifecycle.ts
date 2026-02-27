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
import { extractDuration, fetchCode } from "../api";
import { DEFAULT_DURATION, type GenerateVideoResult, MAX_ATTEMPTS, type Phase } from "../types";

export interface VideoLifecycleState {
	phase: Phase;
	attempt: number;
	component: ComponentType | null;
	durationInFrames: number;
	finalError: string | null;
	generationId: number;
	playerRef: RefObject<PlayerRef | null>;
}

// Captures everything the loop needs so the effect only depends on this one value,
// not on `result` directly — avoids re-running the loop if the result object reference changes.
type GenerationTrigger = {
	result: GenerateVideoResult;
	startAttempt: number;
	lastError?: string;
} | null;

export function useVideoLifecycle(result: GenerateVideoResult | null): VideoLifecycleState {
	const [phase, setPhase] = useState<Phase>("idle");
	const [attempt, setAttempt] = useState(0);
	const [component, setComponent] = useState<ComponentType | null>(null);
	const [durationInFrames, setDurationInFrames] = useState(DEFAULT_DURATION);
	const [finalError, setFinalError] = useState<string | null>(null);
	const [generationId, setGenerationId] = useState(0);

	const [trigger, setTrigger] = useState<GenerationTrigger>(null);

	const playerRef = useRef<PlayerRef | null>(null);
	const attemptRef = useRef(0);

	// starts the loop when the tool result arrives
	useEffect(() => {
		if (!result || result.status !== "prompt_ready") return;
		setTrigger({ result, startAttempt: 1 });
	}, [result]);

	// single generation loop — handles both initial generation and runtime-error retries
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
						controller.signal
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
					setPhase("success");
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

	// stable callback — kicks off the next attempt with the runtime error as context for the LLM
	const onRuntimeError = useCallback((errorMessage: string) => {
		const nextAttempt = attemptRef.current + 1;
		if (nextAttempt > MAX_ATTEMPTS) {
			setFinalError(errorMessage);
			setPhase("failed");
			return;
		}
		setTrigger((prev) =>
			prev ? { result: prev.result, startAttempt: nextAttempt, lastError: errorMessage } : null
		);
	}, []);

	// re-attaches when Player remounts after a successful retry (Player uses key={component.toString()})
	useEffect(() => {
		const player = playerRef.current;
		if (!player) return;

		const handleError = (e: { detail: { error: Error } }) => {
			onRuntimeError(e.detail.error.message);
		};

		player.addEventListener("error", handleError);
		return () => player.removeEventListener("error", handleError);
	}, [component, onRuntimeError]);

	return { phase, attempt, component, durationInFrames, finalError, generationId, playerRef };
}
