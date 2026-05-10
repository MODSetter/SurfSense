import type { FC } from "react";
import type { ReasoningItem as ReasoningItemModel } from "../types";
import { ItemHeader } from "./item-header";

/**
 * Renders a ``kind: "reasoning"`` row — pure agent narration with no
 * tool component beneath it. Just the shared header.
 *
 * Native ``<think>`` blocks (model-level reasoning) are NOT rendered
 * here — they live in the body via assistant-ui's ``Reasoning``
 * component.
 */
export const ReasoningItem: FC<{ item: ReasoningItemModel }> = ({ item }) => (
	<ItemHeader title={item.title} status={item.status} items={item.items} itemKey={item.id} />
);
