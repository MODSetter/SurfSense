"use client";

import { ListPlugin } from "@platejs/list/react";
import { KEYS } from "platejs";

import { IndentKit } from "@/components/editor/plugins/indent-kit";
import { BlockList } from "@/components/ui/block-list";

export const ListKit = [
	...IndentKit,
	ListPlugin.configure({
		inject: {
			targetPlugins: [...KEYS.heading, KEYS.p, KEYS.blockquote, KEYS.codeBlock, KEYS.toggle],
		},
		render: {
			belowNodes: BlockList,
		},
	}),
];
