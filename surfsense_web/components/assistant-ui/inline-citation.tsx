"use client";

import { useSetAtom } from "jotai";
import { FileText } from "lucide-react";
import type { FC } from "react";
import { useId, useState } from "react";
import { openCitationPanelAtom } from "@/atoms/citation/citation-panel.atom";
import { useCitationMetadata } from "@/components/assistant-ui/citation-metadata-context";
import { CitationPanelContent } from "@/components/citation-panel/citation-panel";
import { Citation } from "@/components/tool-ui/citation";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useMediaQuery } from "@/hooks/use-media-query";

interface InlineCitationProps {
	chunkId: number;
	isDocsChunk?: boolean;
}

/**
 * Inline citation badge for knowledge-base chunks (numeric chunk IDs).
 *
 * Numeric KB chunks: clicking opens the citation panel in the right
 * sidebar (alongside the chat — does not replace it). The panel shows
 * the cited chunk surrounded by adjacent chunks (via the API's
 * `chunk_window`), with the cited one highlighted and an option to
 * expand the window or jump into the full document via the editor panel.
 *
 * Negative chunk IDs and legacy SurfSense-docs chunks (`isDocsChunk`) render
 * as a static, non-interactive "doc" pill. The SurfSense product-docs feature
 * was removed, so those markers are inert (no fetch, no preview) — they only
 * survive in old persisted messages.
 */
export const InlineCitation: FC<InlineCitationProps> = ({ chunkId, isDocsChunk = false }) => {
	if (chunkId < 0 || isDocsChunk) {
		return (
			<Tooltip>
				<TooltipTrigger asChild>
					<span
						className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
						role="note"
					>
						<FileText className="size-3" />
						doc
					</span>
				</TooltipTrigger>
				<TooltipContent>
					{isDocsChunk ? "Documentation reference" : "Uploaded document"}
				</TooltipContent>
			</Tooltip>
		);
	}

	return <NumericChunkCitation chunkId={chunkId} />;
};

const NumericChunkCitation: FC<{ chunkId: number }> = ({ chunkId }) => {
	const isTouchLike = useMediaQuery("(hover: none), (pointer: coarse)");
	const openCitationPanel = useSetAtom(openCitationPanelAtom);
	const [mobilePreviewOpen, setMobilePreviewOpen] = useState(false);

	const handleClick = () => {
		if (isTouchLike) {
			setMobilePreviewOpen(true);
			return;
		}
		openCitationPanel({ chunkId });
	};

	return (
		<>
			<Button
				type="button"
				variant="ghost"
				onClick={handleClick}
				className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-md bg-popover px-1.5 text-[11px] font-medium text-popover-foreground/80 align-baseline"
				title={`View source chunk #${chunkId}`}
				aria-label={`View cited chunk ${chunkId}`}
			>
				{chunkId}
			</Button>
			<Drawer
				open={mobilePreviewOpen}
				onOpenChange={setMobilePreviewOpen}
				shouldScaleBackground={false}
			>
				<DrawerContent
					className="h-[85vh] max-h-[85vh] z-80 overflow-hidden"
					overlayClassName="z-80"
				>
					<DrawerHandle />
					<DrawerHeader className="pb-0">
						<DrawerTitle>Citation</DrawerTitle>
					</DrawerHeader>
					<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
						<CitationPanelContent chunkId={chunkId} showHeader={false} />
					</div>
				</DrawerContent>
			</Drawer>
		</>
	);
};

import { tryGetHostname } from "@/lib/url";

interface UrlCitationProps {
	url: string;
}

/**
 * Inline citation for URL-based chunk IDs (e.g. scraped/linked web pages).
 * Renders a compact chip with favicon + domain and a hover popover showing the
 * page title and snippet when citation metadata is available.
 */
export const UrlCitation: FC<UrlCitationProps> = ({ url }) => {
	const reactId = useId();
	const citationInstanceId = `url-cite-${reactId.replace(/:/g, "")}`;
	const domain = tryGetHostname(url) ?? url;
	const meta = useCitationMetadata(url);

	return (
		<Citation
			id={citationInstanceId}
			href={url}
			title={meta?.title || domain}
			snippet={meta?.snippet}
			domain={domain}
			favicon={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
			variant="inline"
			type="webpage"
		/>
	);
};
