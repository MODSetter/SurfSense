"use client";

import type { Separator } from "fumadocs-core/page-tree";

export function SidebarSeparator({ item }: { item: Separator }) {
	return (
		<p className="inline-flex items-center gap-2 mb-1.5 px-2 mt-6 font-semibold first:mt-0 empty:mb-0">
			{item.icon}
			{item.name}
		</p>
	);
}
