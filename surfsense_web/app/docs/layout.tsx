import { DocsLayout } from "fumadocs-ui/layouts/docs";
import type { ReactNode } from "react";
import { baseOptions } from "@/app/layout.config";
import { source } from "@/lib/source";
import { SidebarSeparator } from "./sidebar-separator";

const gridTemplate = `"sidebar header toc"
"sidebar toc-popover toc"
"sidebar main toc" 1fr / var(--fd-sidebar-col) minmax(0, 1fr) min-content`;

export default function Layout({ children }: { children: ReactNode }) {
	return (
		<DocsLayout
			tree={source.pageTree}
			{...baseOptions}
			containerProps={{ style: { gridTemplate }, className: "bg-fd-card" }}
			sidebar={{
				components: {
					Separator: SidebarSeparator,
				},
			}}
		>
			{children}
		</DocsLayout>
	);
}
