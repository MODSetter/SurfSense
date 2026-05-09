"use client";

import type { FC } from "react";
import { getToolDisplayName } from "@/contracts/enums/toolIcons";
import { resolveItemTitle } from "../subagent-rename";
import { adaptItemToProps, FallbackToolBody, getToolComponent } from "../tool-registry";
import type { ToolCallItem as ToolCallItemModel } from "../types";
import { ItemHeader } from "./item-header";

/**
 * Renders a tool-call row. Pending HITL interrupts are filtered
 * upstream in ``buildTimeline`` (owned by ``HitlApprovalCard``); this
 * component only sees running / completed / errored / decided rows.
 */
export const ToolCallItem: FC<{ item: ToolCallItemModel }> = ({ item }) => {
	const title = resolveItemTitle(item, getToolDisplayName);
	const Body = getToolComponent(item.toolName) ?? FallbackToolBody;
	const props = adaptItemToProps(item);

	return (
		<>
			<ItemHeader title={title} status={item.status} items={item.items} itemKey={item.id} />
			<Body {...props} />
		</>
	);
};
