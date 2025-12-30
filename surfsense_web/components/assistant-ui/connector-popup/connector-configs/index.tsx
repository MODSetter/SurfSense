"use client";

import type { FC } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { GoogleDriveConfig } from "./components/google-drive-config";

export interface ConnectorConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
}

export type ConnectorConfigComponent = FC<ConnectorConfigProps>;

/**
 * Factory function to get the appropriate config component for a connector type
 */
export function getConnectorConfigComponent(
	connectorType: string
): ConnectorConfigComponent | null {
	switch (connectorType) {
		case "GOOGLE_DRIVE_CONNECTOR":
			return GoogleDriveConfig;
		// OAuth connectors (Gmail, Calendar, Airtable) and others don't need special config UI
		default:
			return null;
	}
}

