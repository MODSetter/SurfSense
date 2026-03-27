"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useMemo } from "react";
import { queries } from "@/zero/queries";

/**
 * Real-time document type counts derived from Zero's live document sync.
 * Updates instantly as documents are created, deleted, or change type.
 */
export function useZeroDocumentTypeCounts(
	searchSpaceId: number | string | null
): Record<string, number> | undefined {
	const numericId = searchSpaceId != null ? Number(searchSpaceId) : null;

	const [zeroDocuments] = useQuery(
		queries.documents.bySpace({ searchSpaceId: numericId ?? -1 })
	);

	return useMemo(() => {
		if (!zeroDocuments || numericId == null) return undefined;

		const counts: Record<string, number> = {};
		for (const doc of zeroDocuments) {
			if (doc.id != null && doc.title != null && doc.title !== "") {
				counts[doc.documentType] = (counts[doc.documentType] || 0) + 1;
			}
		}
		return counts;
	}, [zeroDocuments, numericId]);
}
