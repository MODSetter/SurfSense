import { DocsLayout } from "fumadocs-ui/layouts/spacious";
import type { ReactNode } from "react";
import { baseOptions } from "@/app/layout.config";
import { source } from "@/features/docs/source";

export default function Layout({ children }: { children: ReactNode }) {
	return (
		<DocsLayout tree={source.pageTree} {...baseOptions}>
			{children}
		</DocsLayout>
	);
}
