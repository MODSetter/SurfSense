// Main component export
export { ConnectorIndicator } from "../connector-popup";

// Sub-components (if needed for external use)
export { ConnectorCard } from "./connector-card";
export { DateRangeSelector } from "./date-range-selector";
export { PeriodicSyncConfig } from "./periodic-sync-config";
export { IndexingConfigurationView } from "./indexing-configuration-view";
export { ConnectorDialogHeader } from "./connector-dialog-header";
export { AllConnectorsTab } from "./all-connectors-tab";
export { ActiveConnectorsTab } from "./active-connectors-tab";

// Constants and types
export { OAUTH_CONNECTORS, OTHER_CONNECTORS } from "./connector-constants";
export type { IndexingConfigState } from "./connector-constants";

// Schemas and validation
export {
	connectorPopupQueryParamsSchema,
	oauthAuthResponseSchema,
	indexingConfigStateSchema,
	frequencyMinutesSchema,
	dateRangeSchema,
	parseConnectorPopupQueryParams,
	parseOAuthAuthResponse,
	validateIndexingConfigState,
} from "./connector-popup.schemas";
export type {
	ConnectorPopupQueryParams,
	OAuthAuthResponse,
	FrequencyMinutes,
	DateRange,
} from "./connector-popup.schemas";

// Hooks
export { useConnectorDialog } from "./use-connector-dialog";

