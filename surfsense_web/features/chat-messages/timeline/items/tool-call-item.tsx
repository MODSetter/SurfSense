"use client";

import type { FC } from "react";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import { ToolCallIdProvider, useHitlBundle } from "@/features/chat-messages/hitl";
import { resolveItemTitle } from "../subagent-rename";
import { adaptItemToProps, FallbackToolBody, getToolComponent } from "../tool-registry";
import type { ToolCallItem as ToolCallItemModel } from "../types";
import { ItemHeader } from "./item-header";

/**
 * Renders a ``kind: "tool-call"`` row: ``ItemHeader`` (title + items)
 * plus the resolved tool body underneath.
 *
 * Tool body is selected from the registry; unknown names fall through
 * to ``FallbackToolBody`` (which itself dispatches between HITL
 * approval cards and the default visual card based on result shape).
 *
 * Multi-approval bundle behaviour: when the HITL bundle is active, all
 * cards EXCEPT the current step are hidden so the user is paged
 * through them one at a time. Hiding is local to this row — the header
 * and the timeline chrome around it are unaffected (the row collapses
 * to its header only). The bundle's ``PagerChrome`` is mounted once
 * at the end of the timeline by ``timeline.tsx``.
 *
 * Every tool body is wrapped in ``ToolCallIdProvider`` so
 * ``useHitlDecision`` (called inside HITL approval cards) can read the
 * tool-call id from context and stage decisions in the bundle.
 */
export const ToolCallItem: FC<{ item: ToolCallItemModel }> = ({ item }) => {
	const bundle = useHitlBundle();
	const hideForBundle =
		bundle?.isInBundle(item.toolCallId) === true && !bundle.isCurrentStep(item.toolCallId);

	const title = resolveItemTitle(item, getToolDisplayName);

	const Body = getToolComponent(item.toolName) ?? FallbackToolBody;
	const props = adaptItemToProps(item);

	return (
		<>
			<ItemHeader title={title} status={item.status} items={item.items} itemKey={item.id} />
			{!hideForBundle && (
				<ToolCallIdProvider toolCallId={item.toolCallId}>
					<Body {...props} />
				</ToolCallIdProvider>
			)}
		</>
	);
};
