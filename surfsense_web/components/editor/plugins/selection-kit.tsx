"use client";

import { BlockSelectionPlugin } from "@platejs/selection/react";

import { BlockSelection } from "@/components/ui/block-selection";

export const SelectionKit = [
	BlockSelectionPlugin.configure({
		render: {
			belowRootNodes: BlockSelection as any,
		},
		options: {
			isSelectable: (element) => {
				// Exclude specific block types from selection
				if (["code_line", "td", "th"].includes(element.type as string)) {
					return false;
				}

				return true;
			},
		},
	}),
];
