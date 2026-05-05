"use client";

import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";
import type { HitlDecision } from "./types";

export type BundleSubmit = (orderedDecisions: HitlDecision[]) => void;

export interface HitlBundleAPI {
	toolCallIds: readonly string[];
	currentStep: number;
	stagedCount: number;
	isInBundle: (toolCallId: string) => boolean;
	isCurrentStep: (toolCallId: string) => boolean;
	getStaged: (toolCallId: string) => HitlDecision | undefined;
	stage: (toolCallId: string, decision: HitlDecision) => void;
	goToStep: (i: number) => void;
	next: () => void;
	prev: () => void;
	submit: () => void;
}

const HitlBundleContext = createContext<HitlBundleAPI | null>(null);
const ToolCallIdContext = createContext<string | null>(null);

export function useHitlBundle(): HitlBundleAPI | null {
	return useContext(HitlBundleContext);
}

export function useToolCallIdContext(): string | null {
	return useContext(ToolCallIdContext);
}

export function ToolCallIdProvider({
	toolCallId,
	children,
}: {
	toolCallId: string;
	children: ReactNode;
}) {
	return <ToolCallIdContext.Provider value={toolCallId}>{children}</ToolCallIdContext.Provider>;
}

interface HitlBundleProviderProps {
	toolCallIds: readonly string[] | null;
	onSubmit: BundleSubmit;
	children: ReactNode;
}

/**
 * Activates only when ``toolCallIds`` has 2+ entries; single-card interrupts
 * keep their direct ``window`` dispatch path so N=1 UX is unchanged.
 */
export function HitlBundleProvider({ toolCallIds, onSubmit, children }: HitlBundleProviderProps) {
	const active = toolCallIds !== null && toolCallIds.length >= 2;
	const ids = useMemo(() => (active ? [...toolCallIds] : []), [active, toolCallIds]);
	const bundleKey = ids.join("|");

	// Derived-state-from-props: reset staging + step when the bundle changes.
	const [prevBundleKey, setPrevBundleKey] = useState(bundleKey);
	const [staged, setStaged] = useState<Map<string, HitlDecision>>(() => new Map());
	const [currentStep, setCurrentStep] = useState(0);
	if (bundleKey !== prevBundleKey) {
		setPrevBundleKey(bundleKey);
		setStaged(new Map());
		setCurrentStep(0);
	}

	const isInBundle = useCallback((tcId: string) => ids.includes(tcId), [ids]);
	const isCurrentStep = useCallback(
		(tcId: string) => active === true && ids[currentStep] === tcId,
		[active, ids, currentStep]
	);
	const getStaged = useCallback((tcId: string) => staged.get(tcId), [staged]);
	const stage = useCallback(
		(tcId: string, decision: HitlDecision) => {
			if (!active || !ids.includes(tcId)) return;
			setStaged((prev) => {
				const next = new Map(prev);
				next.set(tcId, decision);
				return next;
			});
			// Mirror the staged decision onto the card immediately so prev/next
			// nav doesn't re-show approve/reject buttons for already-decided cards.
			// Submit's ``hitl-decision`` event re-applies these (no-op) and runs
			// the actual resume.
			window.dispatchEvent(
				new CustomEvent("hitl-stage", { detail: { toolCallId: tcId, decision } })
			);
			const idx = ids.indexOf(tcId);
			if (idx >= 0 && idx < ids.length - 1) {
				setCurrentStep(idx + 1);
			}
		},
		[active, ids]
	);
	const goToStep = useCallback(
		(i: number) => {
			if (i < 0 || i >= ids.length) return;
			setCurrentStep(i);
		},
		[ids.length]
	);
	const next = useCallback(() => {
		setCurrentStep((s) => Math.min(s + 1, Math.max(0, ids.length - 1)));
	}, [ids.length]);
	const prev = useCallback(() => {
		setCurrentStep((s) => Math.max(s - 1, 0));
	}, []);

	const submit = useCallback(() => {
		if (!active) return;
		if (staged.size !== ids.length) return;
		const ordered: HitlDecision[] = [];
		for (const tcId of ids) {
			const d = staged.get(tcId);
			if (!d) return;
			ordered.push(d);
		}
		onSubmit(ordered);
	}, [active, ids, staged, onSubmit]);

	const value = useMemo<HitlBundleAPI | null>(() => {
		if (!active) return null;
		return {
			toolCallIds: ids,
			currentStep,
			stagedCount: staged.size,
			isInBundle,
			isCurrentStep,
			getStaged,
			stage,
			goToStep,
			next,
			prev,
			submit,
		};
	}, [
		active,
		ids,
		currentStep,
		staged,
		isInBundle,
		isCurrentStep,
		getStaged,
		stage,
		goToStep,
		next,
		prev,
		submit,
	]);

	return <HitlBundleContext.Provider value={value}>{children}</HitlBundleContext.Provider>;
}
