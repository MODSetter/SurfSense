"use client";

import { useCallback, useMemo } from "react";
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
	const getConnectorStatus = useCallback(
		(connectorType: string | undefined): ConnectorStatusConfig => {
			if (!connectorType) {
				return getDefaultConnectorStatus();
			}

			return connectorStatusConfig.connectorStatuses[connectorType] || getDefaultConnectorStatus();
		},
		[]
	);

	/**
	 * Check if a connector is enabled
	 */
	const isConnectorEnabled = useCallback(
		(connectorType: string | undefined): boolean => {
			return getConnectorStatus(connectorType).enabled;
		},
		[getConnectorStatus]
	);

	/**
	 * Get status message for a connector
	 */
	const getConnectorStatusMessage = useCallback(
		(connectorType: string | undefined): string | null => {
			return getConnectorStatus(connectorType).statusMessage || null;
		},
		[getConnectorStatus]
	);

	/**
	 * Check if warnings should be shown globally
	 */
	const shouldShowWarnings = useCallback((): boolean => {
		return connectorStatusConfig.globalSettings.showWarnings;
	}, []);

	return useMemo(
		() => ({
			getConnectorStatus,
			isConnectorEnabled,
			getConnectorStatusMessage,
			shouldShowWarnings,
		}),
		[getConnectorStatus, isConnectorEnabled, getConnectorStatusMessage, shouldShowWarnings]
	);
}
