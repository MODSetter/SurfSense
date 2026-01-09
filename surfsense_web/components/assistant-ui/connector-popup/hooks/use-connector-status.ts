"use client";

import { useMemo } from "react";
import {
	type ConnectorStatusConfig,
	connectorStatusConfig,
	getDefaultConnectorStatus,
} from "../config/connector-status-config";

/**
 * Hook to get connector status information
 */
export function useConnectorStatus() {
	/**
	 * Get status configuration for a specific connector type
	 */
	const getConnectorStatus = (connectorType: string | undefined): ConnectorStatusConfig => {
		if (!connectorType) {
			return getDefaultConnectorStatus();
		}

		return connectorStatusConfig.connectorStatuses[connectorType] || getDefaultConnectorStatus();
	};

	/**
	 * Check if a connector is enabled
	 */
	const isConnectorEnabled = (connectorType: string | undefined): boolean => {
		return getConnectorStatus(connectorType).enabled;
	};

	/**
	 * Get status message for a connector
	 */
	const getConnectorStatusMessage = (connectorType: string | undefined): string | null => {
		return getConnectorStatus(connectorType).statusMessage || null;
	};

	/**
	 * Check if warnings should be shown globally
	 */
	const shouldShowWarnings = (): boolean => {
		return connectorStatusConfig.globalSettings.showWarnings;
	};

	return useMemo(
		() => ({
			getConnectorStatus,
			isConnectorEnabled,
			getConnectorStatusMessage,
			shouldShowWarnings,
		}),
		[]
	);
}
