"use client";

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { statusInboxItemsAtom } from "@/atoms/inbox/status-inbox.atom";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { connectorIndexingMetadata } from "@/contracts/types/inbox.types";
import { type ConnectorTypeRow, groupConnectorsByType } from "../constants/connector-constants";
import { useIndexingConnectors } from "./use-indexing-connectors";

/** Health of a connected connector type, derived from indexing + inbox state. */
export type ConnectorHealth = "syncing" | "failed" | "ok";

/** A grouped connector row enriched with live indexing health. */
export interface ConnectorRow extends ConnectorTypeRow {
	health: ConnectorHealth;
	errorMessage?: string;
}

/**
 * Single source of truth for the "Your connectors" list: groups the connectors
 * by type and derives each row's health (syncing > failed > ok) from the status
 * inbox and optimistic indexing state. Shared by the connectors panel rail and
 * the composer add-menu so both render identical status glyphs.
 *
 * Also returns the underlying indexing controls so the panel can reuse them for
 * its flow views instead of instantiating `useIndexingConnectors` twice.
 */
export function useConnectorRows(connectors: SearchSourceConnector[]) {
	const statusInboxItems = useAtomValue(statusInboxItemsAtom);
	const inboxItems = useMemo(
		() => statusInboxItems.filter((item) => item.type === "connector_indexing"),
		[statusInboxItems]
	);

	const { indexingConnectorIds, startIndexing, stopIndexing } = useIndexingConnectors(
		connectors,
		inboxItems
	);

	// Latest indexing status per connector id, parsed from the status inbox.
	const statusByConnectorId = useMemo(() => {
		const map = new Map<number, { status?: string; error?: string; at: string }>();
		for (const item of inboxItems) {
			const parsed = connectorIndexingMetadata.safeParse(item.metadata);
			if (!parsed.success) continue;
			const at = item.updated_at ?? item.created_at;
			const prev = map.get(parsed.data.connector_id);
			if (!prev || at > prev.at) {
				map.set(parsed.data.connector_id, {
					status: parsed.data.status,
					error: parsed.data.error_message ?? undefined,
					at,
				});
			}
		}
		return map;
	}, [inboxItems]);

	const rows = useMemo<ConnectorRow[]>(() => {
		return groupConnectorsByType(connectors).map((row) => {
			const ids = row.connectors.map((c) => c.id);
			const syncing = ids.some(
				(id) => indexingConnectorIds.has(id) || statusByConnectorId.get(id)?.status === "in_progress"
			);
			const failedEntry = syncing
				? undefined
				: ids.map((id) => statusByConnectorId.get(id)).find((s) => s?.status === "failed");
			return {
				...row,
				health: syncing ? "syncing" : failedEntry ? "failed" : "ok",
				errorMessage: failedEntry?.error,
			} satisfies ConnectorRow;
		});
	}, [connectors, indexingConnectorIds, statusByConnectorId]);

	return { rows, indexingConnectorIds, startIndexing, stopIndexing, inboxItems };
}
