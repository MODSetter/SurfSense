"use client";

import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { createContext, useContext } from "react";
import { isInterruptResult } from "./types";

/**
 * Where this tool-call card is currently rendering.
 *
 * - ``"body"`` (default) — assistant-ui's ``MessagePrimitive.Parts`` renders
 *   the card inside the message bubble.
 * - ``"timeline"`` — ``ThinkingStepsDisplay`` renders the SAME component
 *   inline under the matching step row so the HITL approval lives in the
 *   chain-of-thought instead of as a standalone card in the message body.
 *
 * The two render targets share one component implementation; the context
 * lets the body render skip itself when the timeline copy will show the
 * card, avoiding a double-render.
 */
export type HitlRenderTarget = "body" | "timeline";

const HitlRenderTargetContext = createContext<HitlRenderTarget>("body");

export const HitlRenderTargetProvider = HitlRenderTargetContext.Provider;

export function useHitlRenderTarget(): HitlRenderTarget {
	return useContext(HitlRenderTargetContext);
}

/**
 * Hide the body render of a tool-call whose result is a HITL interrupt.
 * The same component is mounted again inside ``ThinkingStepsDisplay``
 * with ``HitlRenderTargetProvider value="timeline"`` — that copy renders
 * normally, so the card "moves" from the message body to the timeline.
 *
 * Pure pass-through for non-HITL results AND for the timeline render.
 */
export function withHitlInTimeline(
	Component: ToolCallMessagePartComponent
): ToolCallMessagePartComponent {
	const Wrapped: ToolCallMessagePartComponent = (props) => {
		const target = useHitlRenderTarget();
		if (target === "body" && isInterruptResult(props.result)) return null;
		return <Component {...props} />;
	};
	Wrapped.displayName = `withHitlInTimeline(${Component.displayName ?? Component.name ?? "ToolUI"})`;
	return Wrapped;
}
