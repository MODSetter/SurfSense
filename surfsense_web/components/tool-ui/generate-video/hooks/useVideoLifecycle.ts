"use client";

import { compileCode } from "@/app/remotion/compiler";
import type { PlayerRef } from "@remotion/player";
import { useEffect, useRef, useState } from "react";
import { extractDuration, fetchCode } from "../api";
import { DEFAULT_DURATION, MAX_ATTEMPTS, type GenerateVideoResult, type Phase } from "../types";

export interface VideoLifecycleState {
	phase: Phase;
	attempt: number;
	component: React.ComponentType | null;
	durationInFrames: number;
	finalError: string | null;
	playerRef: React.RefObject<PlayerRef | null>;
}

export function useVideoLifecycle(result: GenerateVideoResult | null): VideoLifecycleState {
	const [phase, setPhase] = useState<Phase>("idle");
	const [attempt, setAttempt] = useState(0);
	const [component, setComponent] = useState<React.ComponentType | null>(null);
	const [durationInFrames, setDurationInFrames] = useState(DEFAULT_DURATION);
	const [finalError, setFinalError] = useState<string | null>(null);
	const [runtimeError, setRuntimeError] = useState<string | null>(null);

	const hasStarted = useRef(false);
	const playerRef = useRef<PlayerRef | null>(null);
	const attemptRef = useRef(0);

	// Initial generation — compilation retry loop
	useEffect(() => {
		if (!result || result.status !== "prompt_ready") return;
		if (hasStarted.current) return;
		hasStarted.current = true;

		(async () => {
			let lastError: string | undefined;

			for (let i = 1; i <= MAX_ATTEMPTS; i++) {
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

	// Player runtime error listener.
	// `component` in deps: Player remounts on component change (via key prop), re-attaching the listener.
	useEffect(() => {
		const player = playerRef.current;
		if (!player) return;

		const handleError = (e: { detail: { error: Error } }) => {
			setRuntimeError(e.detail.error.message);
		};

		player.addEventListener("error", handleError);
		return () => player.removeEventListener("error", handleError);
	}, [component]);

	// Runtime error → retry with the error as context for the LLM.
	useEffect(() => {
		if (!runtimeError || !result) return;

		const nextAttempt = attemptRef.current + 1;
		const errorToFix = runtimeError; // capture before clearing
		setRuntimeError(null);

		if (nextAttempt > MAX_ATTEMPTS) {
			setFinalError(errorToFix);
			setPhase("failed");
			return;
		}

		setPhase("generating");
		setAttempt(nextAttempt);
		attemptRef.current = nextAttempt;

		(async () => {
			let lastError: string = errorToFix;

			// Mini-loop in case the fix itself has a compile error
			for (let i = nextAttempt; i <= MAX_ATTEMPTS; i++) {
				if (i > nextAttempt) {
					setAttempt(i);
					attemptRef.current = i;
				}

				try {
					const code = await fetchCode(
						result.search_space_id,
						result.topic,
						result.source_content,
						i,
						lastError,
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
	}, [runtimeError, result]);

	return { phase, attempt, component, durationInFrames, finalError, playerRef };
}
