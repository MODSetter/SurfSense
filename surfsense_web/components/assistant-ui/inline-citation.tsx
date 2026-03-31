"use client";

import type { FC } from "react";
import { useState } from "react";
import { useCitationMetadata } from "@/components/assistant-ui/citation-metadata-context";
import { SourceDetailPanel } from "@/components/new-chat/source-detail-panel";
import { Citation } from "@/components/tool-ui/citation";

interface InlineCitationProps {
	chunkId: number;
	isDocsChunk?: boolean;
}

/**
 * Inline citation for knowledge-base chunks (numeric chunk IDs).
 * Renders a clickable badge showing the actual chunk ID that opens the SourceDetailPanel.
 */
export const InlineCitation: FC<InlineCitationProps> = ({ chunkId, isDocsChunk = false }) => {
	const [isOpen, setIsOpen] = useState(false);

	return (
		<SourceDetailPanel
			open={isOpen}
			onOpenChange={setIsOpen}
			chunkId={chunkId}
			sourceType={isDocsChunk ? "SURFSENSE_DOCS" : ""}
			title={isDocsChunk ? "Surfsense Documentation" : "Source"}
			description=""
			url=""
			isDocsChunk={isDocsChunk}
		>
			<button
				type="button"
				onClick={() => setIsOpen(true)}
				className="text-[10px] font-bold bg-primary/80 hover:bg-primary text-primary-foreground rounded-full min-w-4 h-4 px-1 inline-flex items-center justify-center align-super cursor-pointer transition-colors ml-0.5"
				title={`View source chunk #${chunkId}`}
			>
				{chunkId}
			</button>
		</SourceDetailPanel>
	);
};

function extractDomain(url: string): string {
	try {
		const hostname = new URL(url).hostname;
		return hostname.replace(/^www\./, "");
	} catch {
		return url;
	}
}

interface UrlCitationProps {
	url: string;
}

/**
 * Inline citation for live web search results (URL-based chunk IDs).
 * Renders a compact chip with favicon + domain and a hover popover showing the
 * page title and snippet (extracted deterministically from web_search tool results).
 */
export const UrlCitation: FC<UrlCitationProps> = ({ url }) => {
	const domain = extractDomain(url);
	const meta = useCitationMetadata(url);

	return (
		<Citation
			id={`url-cite-${url}`}
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
