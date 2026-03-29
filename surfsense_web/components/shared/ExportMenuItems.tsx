"use client";

import { Loader2 } from "lucide-react";
import { ContextMenuItem } from "@/components/ui/context-menu";
import {
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

export const EXPORT_FILE_EXTENSIONS: Record<string, string> = {
	pdf: "pdf",
	docx: "docx",
	html: "html",
	latex: "tex",
	epub: "epub",
	odt: "odt",
	plain: "txt",
	md: "md",
};

interface ExportMenuItemsProps {
	onExport: (format: string) => void;
	exporting: string | null;
	/** Hide server-side formats (PDF, DOCX, etc.) — only show md */
	showAllFormats?: boolean;
}

export function ExportDropdownItems({
	onExport,
	exporting,
	showAllFormats = true,
}: ExportMenuItemsProps) {
	const handle = (format: string) => (e: React.MouseEvent) => {
		e.stopPropagation();
		onExport(format);
	};

	return (
		<>
			{showAllFormats && (
				<>
					<DropdownMenuLabel className="text-xs text-muted-foreground">Documents</DropdownMenuLabel>
					<DropdownMenuItem onClick={handle("pdf")} disabled={exporting !== null}>
						{exporting === "pdf" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						PDF (.pdf)
					</DropdownMenuItem>
					<DropdownMenuItem onClick={handle("docx")} disabled={exporting !== null}>
						{exporting === "docx" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						Word (.docx)
					</DropdownMenuItem>
					<DropdownMenuItem onClick={handle("odt")} disabled={exporting !== null}>
						{exporting === "odt" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						OpenDocument (.odt)
					</DropdownMenuItem>
					<DropdownMenuSeparator />
					<DropdownMenuLabel className="text-xs text-muted-foreground">
						Web &amp; E-Book
					</DropdownMenuLabel>
					<DropdownMenuItem onClick={handle("html")} disabled={exporting !== null}>
						{exporting === "html" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						HTML (.html)
					</DropdownMenuItem>
					<DropdownMenuItem onClick={handle("epub")} disabled={exporting !== null}>
						{exporting === "epub" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						EPUB (.epub)
					</DropdownMenuItem>
					<DropdownMenuSeparator />
					<DropdownMenuLabel className="text-xs text-muted-foreground">
						Source &amp; Plain
					</DropdownMenuLabel>
					<DropdownMenuItem onClick={handle("latex")} disabled={exporting !== null}>
						{exporting === "latex" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						LaTeX (.tex)
					</DropdownMenuItem>
				</>
			)}
			<DropdownMenuItem onClick={handle("md")} disabled={exporting !== null}>
				{exporting === "md" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
				Markdown (.md)
			</DropdownMenuItem>
			{showAllFormats && (
				<DropdownMenuItem onClick={handle("plain")} disabled={exporting !== null}>
					{exporting === "plain" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
					Plain Text (.txt)
				</DropdownMenuItem>
			)}
		</>
	);
}

export function ExportContextItems({
	onExport,
	exporting,
	showAllFormats = true,
}: ExportMenuItemsProps) {
	const handle = (format: string) => (e: React.MouseEvent) => {
		e.stopPropagation();
		onExport(format);
	};

	return (
		<>
			{showAllFormats && (
				<>
					<ContextMenuItem onClick={handle("pdf")} disabled={exporting !== null}>
						{exporting === "pdf" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						PDF (.pdf)
					</ContextMenuItem>
					<ContextMenuItem onClick={handle("docx")} disabled={exporting !== null}>
						{exporting === "docx" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						Word (.docx)
					</ContextMenuItem>
					<ContextMenuItem onClick={handle("odt")} disabled={exporting !== null}>
						{exporting === "odt" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						OpenDocument (.odt)
					</ContextMenuItem>
					<ContextMenuItem onClick={handle("html")} disabled={exporting !== null}>
						{exporting === "html" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						HTML (.html)
					</ContextMenuItem>
					<ContextMenuItem onClick={handle("epub")} disabled={exporting !== null}>
						{exporting === "epub" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						EPUB (.epub)
					</ContextMenuItem>
					<ContextMenuItem onClick={handle("latex")} disabled={exporting !== null}>
						{exporting === "latex" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
						LaTeX (.tex)
					</ContextMenuItem>
				</>
			)}
			<ContextMenuItem onClick={handle("md")} disabled={exporting !== null}>
				{exporting === "md" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
				Markdown (.md)
			</ContextMenuItem>
			{showAllFormats && (
				<ContextMenuItem onClick={handle("plain")} disabled={exporting !== null}>
					{exporting === "plain" && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
					Plain Text (.txt)
				</ContextMenuItem>
			)}
		</>
	);
}
