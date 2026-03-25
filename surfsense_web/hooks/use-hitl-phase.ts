import { useEffect, useRef, useState } from "react";

export type HitlPhase = "pending" | "processing" | "complete" | "rejected";

interface HitlInterruptLike {
	__decided__?: string | null;
	__completed__?: boolean;
}

const MINIMUM_SHIMMER_MS = 500;
const FALLBACK_TIMEOUT_MS = 30_000;

/**
 * State machine for HITL approval card phases.
 *
 * Phases:
 *   pending    – waiting for user decision (show buttons)
 *   processing – user approved/edited, waiting for backend (shimmer)
 *   complete   – backend responded with __completed__ (done text)
 *   rejected   – user rejected (cancelled text)
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

	// processing → complete when __completed__ arrives (with min shimmer duration)
	useEffect(() => {
		if (phase !== "processing") return;
		if (!interruptData.__completed__) return;

		const elapsed = shimmerStartRef.current ? Date.now() - shimmerStartRef.current : Infinity;
		const remaining = Math.max(0, MINIMUM_SHIMMER_MS - elapsed);

		const timer = setTimeout(() => setPhase("complete"), remaining);
		return () => clearTimeout(timer);
	}, [phase, interruptData.__completed__]);

	// Fallback: processing → complete after 30s even if __completed__ never arrives
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
