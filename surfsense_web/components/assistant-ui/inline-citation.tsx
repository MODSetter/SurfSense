"use client";

import type { FC } from "react";
import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { SourceDetailPanel } from "@/components/new-chat/source-detail-panel";

interface InlineCitationProps {
	chunkId: number;
	isDocsChunk?: boolean;
}

/**
 * Inline citation for knowledge-base chunks (numeric chunk IDs).
 * Renders a clickable badge showing the actual chunk ID that opens the SourceDetailPanel.
 */
export const InlineCitation: FC<InlineCitationProps> = ({
	chunkId,
	isDocsChunk = false,
}) => {
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
			<span
				onClick={() => setIsOpen(true)}
				onKeyDown={(e) => e.key === "Enter" && setIsOpen(true)}
				className="text-[10px] font-bold bg-primary/80 hover:bg-primary text-primary-foreground rounded-full min-w-4 h-4 px-1 inline-flex items-center justify-center align-super cursor-pointer transition-colors ml-0.5"
				title={`View source chunk #${chunkId}`}
				role="button"
				tabIndex={0}
			>
				{chunkId}
			</span>
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
 * Renders a clickable badge showing the source domain that opens the URL in a new tab.
 */
export const UrlCitation: FC<UrlCitationProps> = ({ url }) => {
	const domain = extractDomain(url);

	return (
		<a
			href={url}
			target="_blank"
			rel="noopener noreferrer"
			className="text-[10px] font-bold bg-primary/80 hover:bg-primary text-primary-foreground rounded-full h-4 px-1.5 inline-flex items-center gap-0.5 align-super cursor-pointer transition-colors ml-0.5 no-underline"
			title={url}
		>
			<ExternalLink className="size-2.5 shrink-0" />
			{domain}
		</a>
	);
};
