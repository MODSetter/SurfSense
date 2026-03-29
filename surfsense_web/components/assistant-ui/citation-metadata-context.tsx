"use client";

import { useAuiState } from "@assistant-ui/react";
import { createContext, type FC, type ReactNode, useContext, useMemo } from "react";

export interface CitationMeta {
	title: string;
	snippet?: string;
}

type CitationMetadataMap = ReadonlyMap<string, CitationMeta>;

const CitationMetadataContext = createContext<CitationMetadataMap>(new Map());

interface ToolCallResult {
	status?: string;
	citations?: Record<string, { title: string; snippet?: string }>;
}

interface MessageContent {
	type: string;
	toolName?: string;
	result?: unknown;
}

export const CitationMetadataProvider: FC<{ children: ReactNode }> = ({ children }) => {
	const content = useAuiState(
		({ message }) => (message as { content?: MessageContent[] })?.content
	);

	const metadataMap = useMemo<CitationMetadataMap>(() => {
		if (!content || !Array.isArray(content)) return new Map();

		const merged = new Map<string, CitationMeta>();

		for (const part of content) {
			if (part.type !== "tool-call" || part.toolName !== "web_search" || !part.result) {
				continue;
			}

			const result = part.result as ToolCallResult;
			const citations = result.citations;
			if (!citations || typeof citations !== "object") continue;

			for (const [url, meta] of Object.entries(citations)) {
				if (url.startsWith("http") && meta.title && !merged.has(url)) {
					merged.set(url, { title: meta.title, snippet: meta.snippet });
				}
			}
		}

		return merged;
	}, [content]);

	return (
		<CitationMetadataContext.Provider value={metadataMap}>
			{children}
		</CitationMetadataContext.Provider>
	);
};

export function useCitationMetadata(url: string): CitationMeta | undefined {
	const map = useContext(CitationMetadataContext);
	return map.get(url);
}

export function useAllCitationMetadata(): CitationMetadataMap {
	return useContext(CitationMetadataContext);
}
