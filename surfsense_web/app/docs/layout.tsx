import { DocsLayout } from "fumadocs-ui/layouts/docs";
import type { ReactNode } from "react";
import { baseOptions } from "@/app/layout.config";
import { siteSansFont } from "@/components/site/site-sans-font";
import { source } from "@/lib/source";
import { SidebarSeparator } from "./sidebar-separator";

const gridTemplate = `"sidebar header toc"
"sidebar toc-popover toc"
"sidebar main toc" 1fr / var(--fd-sidebar-col) minmax(0, 1fr) min-content`;

const docsSurfaceClass =
	"bg-main-panel [--color-fd-background:var(--main-panel)] [--color-fd-card:var(--main-panel)] [--color-fd-popover:var(--main-panel)] [--color-fd-muted:var(--main-panel)] [--color-fd-secondary:var(--main-panel)]";

// Set on body, not a wrapper, so the portalled search dialog follows it. Mounted
// with this layout, so it is dropped on navigating out of /docs.
// `:root body` outranks the root layout's Roboto class on body.
const docsFontStyle = `:root body{--font-sans:${siteSansFont.style.fontFamily};font-family:var(--font-sans)}`;

export default function Layout({ children }: { children: ReactNode }) {
	return (
		<>
			<style>{docsFontStyle}</style>
			<DocsLayout
				tree={source.pageTree}
				{...baseOptions}
				containerProps={{ style: { gridTemplate }, className: docsSurfaceClass }}
				sidebar={{
					components: {
						Separator: SidebarSeparator,
					},
				}}
			>
				{children}
			</DocsLayout>
		</>
	);
}
