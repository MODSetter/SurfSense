"use client";

import { BookOpen } from "lucide-react";
import type { FC } from "react";
import {
	getConnectorLogo,
	getToolPresentation,
	inferNativeIntegration,
	resolvePresentationTitle,
} from "../presentation";
import type { ToolCallItem as ToolCallItemModel } from "../types";
import { ItemHeader } from "./item-header";

/**
 * Renders a tool-call row. Pending HITL interrupts are filtered
 * upstream in ``buildTimeline`` (owned by ``HitlApprovalCard``); this
 * component only sees running / completed / errored / decided rows.
 */
export const ToolCallItem: FC<{ item: ToolCallItemModel }> = ({ item }) => {
	const presentation = getToolPresentation(item.toolName);
	const integration = item.integration ?? inferNativeIntegration(item.toolName);
	const Icon = item.context?.intent === "discover_skill" ? BookOpen : presentation.icon;
	const explicitTitle =
		item.status === "running" || item.status === "pending"
			? item.activeTitle
			: item.status === "completed"
				? item.completedTitle
				: undefined;
	const title =
		explicitTitle ??
		(item.toolName === "task" ? presentation.completed : resolvePresentationTitle(item));

	return (
		<ItemHeader
			title={title}
			status={item.status}
			icon={Icon}
			logo={getConnectorLogo(integration)}
		/>
	);
};
