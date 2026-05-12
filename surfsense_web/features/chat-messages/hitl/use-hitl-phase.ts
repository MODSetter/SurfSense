import { useEffect, useRef, useState } from "react";
import type { HitlPhase } from "./types";

interface HitlInterruptLike {
	__decided__?: string | null;
	__completed__?: boolean;
}

const MINIMUM_SHIMMER_MS = 500;
const FALLBACK_TIMEOUT_MS = 30_000;

/**
 * Local UI state machine for a HITL approval card.
 *
 * Phase transitions:
 *   pending    → user has not yet decided (show approve/edit/reject buttons)
 *   processing → user clicked; awaiting backend confirmation (shimmer)
 *   complete   → backend acknowledged via __completed__ (or fallback timeout)
 *   rejected   → user explicitly rejected (terminal state, no backend wait)
 *
 * Initial phase is derived from the current ``__decided__`` /
 * ``__completed__`` markers on the result, so cards rehydrate
 * correctly from persisted history.
 *
 * NOT shared across cards. Each approval card calls ``useHitlPhase``
 * once with its own interrupt result.
 */
export function useHitlPhase(interruptData: HitlInterruptLike): {
	phase: HitlPhase;
	setProcessing: () => void;
	setRejected: () => void;
} {
	const [phase, setPhase] = useState<HitlPhase>(() => {
		if (interruptData.__decided__ === "reject") return "rejected";
		if (interruptData.__decided__) return "complete";
		return "pending";
	});

	const shimmerStartRef = useRef<number | null>(null);

	useEffect(() => {
		if (phase !== "processing") return;
		if (!interruptData.__completed__) return;

		const elapsed = shimmerStartRef.current ? Date.now() - shimmerStartRef.current : Infinity;
		const remaining = Math.max(0, MINIMUM_SHIMMER_MS - elapsed);

		const timer = setTimeout(() => setPhase("complete"), remaining);
		return () => clearTimeout(timer);
	}, [phase, interruptData.__completed__]);

	useEffect(() => {
		if (phase !== "processing") return;
		const fallback = setTimeout(() => setPhase("complete"), FALLBACK_TIMEOUT_MS);
		return () => clearTimeout(fallback);
	}, [phase]);

	return {
		phase,
		setProcessing: () => {
			shimmerStartRef.current = Date.now();
			setPhase("processing");
		},
		setRejected: () => setPhase("rejected"),
	};
}
