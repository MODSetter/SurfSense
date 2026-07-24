"use client";

import { createContext, type FC, type ReactNode, useContext } from "react";

export interface CitationMeta {
	title: string;
	snippet?: string;
}

type CitationMetadataMap = ReadonlyMap<string, CitationMeta>;

const EMPTY_CITATION_METADATA: CitationMetadataMap = new Map();

const CitationMetadataContext = createContext<CitationMetadataMap>(EMPTY_CITATION_METADATA);

// The previous web-search citation spine (WEB_RESULT hover cards) was removed
// with the multi-engine web_search tool. Agent citation logic is being reworked
// wholesale, so this provider currently yields no web citation metadata.
export const CitationMetadataProvider: FC<{ children: ReactNode }> = ({ children }) => {
	return (
		<CitationMetadataContext.Provider value={EMPTY_CITATION_METADATA}>
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
