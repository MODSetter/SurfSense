import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type FormatFileProps =
	| "doc"
	| "pdf"
	| "md"
	| "mdx"
	| "csv"
	| "xls"
	| "xlsx"
	| "txt"
	| "ppt"
	| "pptx"
	| "zip"
	| "rar"
	| "tar"
	| "gz"
	| "code"
	| "html"
	| "js"
	| "jsx"
	| "tsx"
	| "css"
	| "json"
	| "img"
	| "png"
	| "jpg"
	| "jpeg"
	| "video";

type FileCardProps = {
	formatFile: FormatFileProps;
};

const DefaultPlaceholder = () => {
	return (
		<div className="space-y-1.5">
			<div className="flex gap-2">
				<div className="bg-foreground/20 h-0.5 w-1/2 rounded-full" />
			</div>
			<div className="flex gap-1">
				<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
				<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
			</div>
			<div className="flex gap-1">
				<div className="bg-foreground/10 h-0.5 w-1/2 rounded-full" />
				<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
			</div>
			<div className="flex gap-1">
				<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
				<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
			</div>
			<div className="flex gap-1">
				<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
				<div className="bg-foreground/10 h-0.5 w-1/2 rounded-full" />
			</div>
			<div className="flex gap-1">
				<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
			</div>
		</div>
	);
};

const colorBannerMap: Record<FormatFileProps, string> = {
	doc: "bg-blue-500 text-white",
	pdf: "bg-red-500 text-white",
	md: "bg-neutral-600 text-white",
	mdx: "bg-neutral-600 text-white",
	txt: "bg-gray-500 text-white",
	csv: "bg-teal-700 text-white",
	xls: "bg-emerald-600 text-white",
	xlsx: "bg-emerald-600 text-white",
	ppt: "bg-orange-500 text-white",
	pptx: "bg-orange-500 text-white",
	zip: "bg-purple-500 text-white",
	rar: "bg-purple-600 text-white",
	tar: "bg-yellow-600 text-white",
	gz: "bg-yellow-700 text-white",
	html: "bg-orange-600 text-white",
	js: "bg-yellow-600 text-white",
	jsx: "bg-blue-600 text-white",
	css: "bg-blue-600 text-white",
	json: "bg-yellow-500 text-white",
	tsx: "bg-blue-600 text-white",
	code: "bg-orange-600 text-white",
	img: "bg-pink-500 text-white",
	png: "bg-neutral-600 text-white",
	jpg: "bg-green-700 text-white",
	jpeg: "bg-green-700 text-white",
	video: "bg-green-700 text-white",
};

export const FileCard = ({ formatFile }: FileCardProps) => {
	const colorBannerClass = colorBannerMap[formatFile];
	let filePlaceholder: ReactNode = null;

	filePlaceholder = <DefaultPlaceholder />;

	if (formatFile === "md" || formatFile === "mdx") {
		filePlaceholder = (
			<div className="space-y-1.5">
				<div className="flex items-center gap-1">
					<div className="text-foreground/30 text-[10px] font-bold">#</div>
					<div className="bg-foreground/20 h-0.5 w-6 rounded-full" />
				</div>
				<div className="space-y-1">
					<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
					<div className="bg-foreground/10 h-0.5 w-7 rounded-full" />
				</div>
				<div className="space-y-1">
					<div className="bg-foreground/10 h-0.5 w-8 rounded-full" />
					<div className="bg-foreground/10 h-0.5 w-4 rounded-full" />
					<div className="bg-foreground/10 h-0.5 w-1/3 rounded-full" />
				</div>
			</div>
		);
	}

	if (formatFile === "xls" || formatFile === "xlsx") {
		filePlaceholder = (
			<div className="space-y-0.5">
				<div className="grid grid-cols-3 gap-0.5">
					<div className="bg-foreground/20 h-2" />
					<div className="bg-foreground/20 h-2" />
					<div className="bg-foreground/20 h-2" />
				</div>
				<div className="grid grid-cols-3 gap-0.5">
					<div className="bg-foreground/5 h-2" />
					<div className="bg-foreground/5 h-2" />
					<div className="bg-foreground/5 h-2" />
					<div className="bg-foreground/5 h-2" />
					<div className="bg-foreground/5 h-2" />
					<div className="bg-foreground/5 h-2" />
				</div>
				<div className="grid grid-cols-3 gap-0.5">
					<div className="bg-foreground/5 h-2" />
					<div className="bg-foreground/5 h-2" />
				</div>
				<div className="grid grid-cols-3 gap-0.5">
					<div className="bg-foreground/5 h-2" />
				</div>
			</div>
		);
	}

	if (formatFile === "csv") {
		filePlaceholder = (
			<>
				<div className="mb-2">
					<div className="grid grid-cols-3 gap-0.5">
						<div className="bg-foreground/20 h-1.5 rounded-full" />
						<div className="bg-foreground/20 h-1.5 rounded-full" />
						<div className="bg-foreground/20 h-1.5 rounded-full" />
					</div>
				</div>
				<div className="space-y-1.5">
					<div className="grid grid-cols-3 gap-0.5">
						<div className="bg-foreground/5 h-1 rounded-full" />
						<div className="bg-foreground/5 h-1 rounded-full" />
						<div className="bg-foreground/5 h-1 rounded-full" />
					</div>
					<div className="grid grid-cols-3 gap-0.5">
						<div className="bg-foreground/5 h-1 rounded-full" />
						<div className="bg-foreground/5 h-1 rounded-full" />
						<div className="bg-foreground/5 h-1 rounded-full" />
					</div>
					<div className="grid grid-cols-3 gap-0.5">
						<div className="bg-foreground/5 h-1 rounded-full" />
						<div className="bg-foreground/5 h-1 rounded-full" />
					</div>
					<div className="grid grid-cols-3 gap-0.5">
						<div className="bg-foreground/5 h-1 rounded-full" />
					</div>
				</div>
			</>
		);
	}

	if (formatFile === "zip" || formatFile === "rar" || formatFile === "tar" || formatFile === "gz") {
		filePlaceholder = (
			<div className="relative flex h-full flex-col items-center justify-center">
				<div className="space-y-0">
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/20 size-1.5" />
						<div className="bg-foreground/5 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/5 size-1.5" />
						<div className="bg-foreground/20 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/20 size-1.5" />
						<div className="bg-foreground/5 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/5 size-1.5" />
						<div className="bg-foreground/20 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/20 size-1.5" />
						<div className="bg-foreground/5 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/5 size-1.5" />
						<div className="bg-foreground/20 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/20 size-1.5" />
						<div className="bg-foreground/5 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/5 size-1.5" />
						<div className="bg-foreground/20 size-1.5" />
					</div>
					<div className="flex overflow-hidden rounded-full">
						<div className="bg-foreground/20 size-1.5" />
						<div className="bg-foreground/5 size-1.5" />
					</div>
				</div>
			</div>
		);
	}

	if (formatFile === "ppt" || formatFile === "pptx") {
		filePlaceholder = (
			<>
				<div className="bg-foreground/5 mb-1.5 space-y-1 rounded border p-1">
					<div className="flex justify-center gap-1">
						<div className="size-3 rounded-sm bg-orange-400/40" />
					</div>
					<div className="bg-foreground/15 mx-auto h-0.75 w-8 rounded-full" />
				</div>
				<div className="mb-1 flex justify-center gap-1">
					<div className="bg-foreground/15 h-0.75 w-8 rounded-full" />
					<div className="bg-foreground/15 h-0.75 w-4 rounded-full" />
				</div>
				<div className="space-y-1">
					<div className="bg-foreground/15 h-0.75 w-4 rounded-full" />
					<div className="bg-foreground/15 h-0.75 w-5 rounded-full" />
				</div>
			</>
		);
	}

	if (
		formatFile === "img" ||
		formatFile === "png" ||
		formatFile === "jpg" ||
		formatFile === "jpeg"
	) {
		filePlaceholder = (
			<>
				<div className="bg-foreground/5 mb-1.5 space-y-1 rounded border p-1">
					<div className="flex justify-center gap-1">
						<div className="size-3 rounded-sm bg-yellow-400/40" />
					</div>
					<div className="bg-foreground/15 mx-auto mt-1 h-0.75 w-4 rounded-full" />
					<div className="bg-foreground/15 mx-auto h-0.75 w-8 rounded-full" />
				</div>
			</>
		);
	}

	if (formatFile === "video") {
		filePlaceholder = (
			<>
				<div className="bg-foreground/5 mb-1.5 space-y-1 rounded border p-1">
					<div className="flex justify-center gap-1">
						<div className="size-0 border-y-[5px] border-l-8 border-y-transparent border-l-green-400/60" />
					</div>
					<div className="bg-foreground/15 mx-auto mt-1 h-0.75 w-4 rounded-full" />
					<div className="bg-foreground/15 mx-auto h-0.75 w-8 rounded-full" />
				</div>
			</>
		);
	}

	if (
		formatFile === "html" ||
		formatFile === "js" ||
		formatFile === "jsx" ||
		formatFile === "tsx" ||
		formatFile === "code"
	) {
		filePlaceholder = (
			<div className="space-y-1">
				<div className="flex items-center gap-0.5">
					<div className="text-foreground/30 font-mono text-[5px]">&lt;</div>
					<div className="h-0.75 w-3 rounded-full bg-emerald-400/60" />
					<div className="text-foreground/30 font-mono text-[5px]">&gt;</div>
				</div>
				<div className="flex items-center gap-0.5 pl-1">
					<div className="text-foreground/30 font-mono text-[5px]">&lt;</div>
					<div className="h-0.75 w-2.5 rounded-full bg-sky-400/60" />
					<div className="text-foreground/30 font-mono text-[5px]">&gt;</div>
				</div>
				<div className="flex items-center gap-0.5 pl-1">
					<div className="text-foreground/30 font-mono text-[5px]">&lt;/</div>
					<div className="h-0.75 w-2.5 rounded-full bg-sky-400/60" />
					<div className="text-foreground/30 font-mono text-[5px]">&gt;</div>
				</div>
				<div className="flex items-center gap-0.5">
					<div className="text-foreground/30 font-mono text-[5px]">&lt;</div>
					<div className="h-0.75 w-1 rounded-full bg-emerald-400/60" />
					<div className="text-foreground/30 font-mono text-[5px]">/&gt;</div>
				</div>
			</div>
		);
	}

	if (formatFile === "css") {
		filePlaceholder = (
			<div className="space-y-1">
				<div className="flex items-center gap-1">
					<div className="text-foreground/40 font-mono text-[6px]">{"{"}</div>
				</div>
				<div className="flex items-center gap-1 pl-1.5">
					<div className="h-0.75 w-3 rounded-full bg-sky-400/60" />
					<div className="h-0.75 w-4 rounded-full bg-sky-400/60" />
				</div>
				<div className="flex items-center gap-1 pl-1.5">
					<div className="h-0.75 w-4 rounded-full bg-sky-400/60" />
					<div className="h-0.75 w-2 rounded-full bg-sky-400/60" />
				</div>
				<div className="flex items-center gap-1 pl-1.5">
					<div className="h-0.75 w-3 rounded-full bg-sky-400/60" />
					<div className="h-0.75 w-4 rounded-full bg-sky-400/60" />
				</div>
				<div className="flex items-center gap-1">
					<div className="text-foreground/40 font-mono text-[6px]">{"}"}</div>
				</div>
			</div>
		);
	}

	if (formatFile === "json") {
		filePlaceholder = (
			<div className="space-y-1">
				<div className="flex items-center gap-1">
					<div className="text-foreground/40 font-mono text-[6px]">{"{"}</div>
				</div>
				<div className="flex items-center gap-1 pl-1.5">
					<div className="bg-foreground/20 h-0.75 w-3 rounded-full" />
					<div className="bg-foreground/20 h-0.75 w-4 rounded-full" />
				</div>
				<div className="flex items-center gap-1 pl-1.5">
					<div className="bg-foreground/10 h-0.75 w-4 rounded-full" />
					<div className="bg-foreground/10 h-0.75 w-2 rounded-full" />
				</div>
				<div className="flex items-center gap-1 pl-1.5">
					<div className="bg-foreground/10 h-0.75 w-3 rounded-full" />
					<div className="bg-foreground/10 h-0.75 w-4 rounded-full" />
				</div>
				<div className="flex items-center gap-1 pl-1.5">
					<div className="bg-foreground/10 h-0.75 w-3 rounded-full" />
				</div>
				<div className="flex items-center gap-1">
					<div className="text-foreground/40 font-mono text-[6px]">{"}"}</div>
				</div>
			</div>
		);
	}

	const sizeClass = "w-14 h-18";

	return (
		<div aria-hidden className="relative size-fit">
			<div
				className={cn(
					"absolute -right-2 bottom-1.5 z-2 rounded px-1.5 py-0.5 text-[8px] font-medium uppercase",
					colorBannerClass
				)}
			>
				{formatFile}
			</div>
			<div
				className={cn(
					"dark:bg-secondary ring-border relative z-1 space-y-3 rounded-md bg-white p-2 ring-1",
					sizeClass
				)}
			>
				{filePlaceholder}
			</div>
		</div>
	);
};

export default FileCard;
