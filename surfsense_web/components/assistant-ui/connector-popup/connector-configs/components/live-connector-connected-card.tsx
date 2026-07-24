"use client";

import { CheckCircle2 } from "lucide-react";
import type { FC } from "react";
import { getConnectorTypeDisplay } from "@/lib/connectors/utils";
import {
	COMPOSIO_CONNECTORS,
	CRAWLERS,
	OAUTH_CONNECTORS,
	OTHER_CONNECTORS,
} from "../../constants/connector-constants";
import type { ConnectorConfigProps } from "../index";

// Catalog descriptions keyed by connector type, reused as the capability line so
// the copy stays in sync with the catalog cards.
const DESCRIPTION_BY_TYPE = new Map<string, string>(
	[...OAUTH_CONNECTORS, ...COMPOSIO_CONNECTORS, ...OTHER_CONNECTORS, ...CRAWLERS].map((c) => [
		c.connectorType,
		c.description,
	])
);

/**
 * Fallback manage view for live connectors that are neither MCP-backed nor have
 * a dedicated config component (native/Composio Gmail & Calendar). There is
 * nothing to configure, so we just confirm the connection and echo what the
 * agent can do — no Trusted Tools (that feature is MCP-only, see the backend
 * `_ensure_mcp_connector_for_user`).
 */
export const LiveConnectorConnectedCard: FC<ConnectorConfigProps> = ({ connector }) => {
	const capability =
		DESCRIPTION_BY_TYPE.get(connector.connector_type) ??
		`connect to ${getConnectorTypeDisplay(connector.connector_type)}`;

	return (
		<div className="space-y-6">
			<div className="rounded-xl border border-border bg-emerald-500/5 p-4 flex items-start gap-3">
				<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 shrink-0 mt-0.5">
					<CheckCircle2 className="size-4 text-emerald-500" />
				</div>
				<div className="text-xs sm:text-sm">
					<p className="font-medium text-xs sm:text-sm">Connected</p>
					<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">{capability}.</p>
				</div>
			</div>
		</div>
	);
};
