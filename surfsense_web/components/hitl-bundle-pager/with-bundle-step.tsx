"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import type { ComponentType } from "react";
import { ToolCallIdProvider, useHitlBundle } from "@/lib/hitl";
import { PagerChrome } from "./pager-chrome";

/**
 * Wrap a tool-ui card so that, when a multi-card HITL bundle is active:
 *  - cards belonging to the bundle but not the current step render ``null``;
 *  - the current-step card renders normally and is followed by ``PagerChrome``.
 *
 * Cards stay completely unchanged — the wrapper provides the
 * ``ToolCallIdContext`` that ``useHitlDecision`` reads to stage decisions
 * against the right ``toolCallId`` instead of firing the global event.
 */
export function withBundleStep<P extends ToolCallMessagePartProps<any, any>>(
	Component: ComponentType<P>
): ComponentType<P> {
	function BundleStepWrapped(props: P) {
		const bundle = useHitlBundle();
		const toolCallId = props.toolCallId;
		const inBundle = bundle?.isInBundle(toolCallId) ?? false;
		const isStep = bundle?.isCurrentStep(toolCallId) ?? false;

		if (bundle && inBundle && !isStep) return null;

		return (
			<ToolCallIdProvider toolCallId={toolCallId}>
				<Component {...props} />
				{bundle && isStep ? <PagerChrome /> : null}
			</ToolCallIdProvider>
		);
	}
	BundleStepWrapped.displayName = `withBundleStep(${Component.displayName ?? Component.name ?? "ToolUI"})`;
	return BundleStepWrapped as ComponentType<P>;
}
