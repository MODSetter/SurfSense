import type { ComponentProps } from "react";
import type { Format } from "@/components/homepage/home/home-content";
import { siteText } from "@/components/site/site-text";
import { FileCard } from "@/components/ui/file-card-collections";
import { cn } from "@/lib/utils";

// The file each written format comes out as.
const FILE_TYPES: Record<string, ComponentProps<typeof FileCard>["formatFile"]> = {
	summary: "md",
	docx: "doc",
	pdf: "pdf",
	html: "html",
	xlsx: "xlsx",
};

/**
 * The written formats as one card of file tiles: they are the same content in
 * different files, so they read as one idea rather than five cards.
 */
export function ReadExportCard({ formats, className }: { formats: Format[]; className?: string }) {
	return (
		<article
			className={cn(
				"rounded-2xl border border-border bg-card px-5 py-6 shadow-xs transition-[translate,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_16px_32px_-16px_rgb(0_0_0/0.2)] motion-reduce:transition-none motion-reduce:hover:translate-y-0",
				className
			)}
		>
			<p className={siteText.eyebrow}>Read and export</p>
			<ul className="m-0 mt-5 grid list-none gap-6 p-0 sm:grid-cols-2 lg:grid-cols-5">
				{formats.map((format) => (
					<li key={format.key} className="flex items-start gap-6">
						<div className="shrink-0">
							<FileCard formatFile={FILE_TYPES[format.key] ?? "txt"} />
						</div>
						<div>
							<p className={siteText.h3}>{format.label}</p>
							<p className={cn(siteText.body, "mt-1 text-sm")}>{format.body}</p>
						</div>
					</li>
				))}
			</ul>
		</article>
	);
}
