// Main component export
export { ConnectorIndicator } from "../connector-popup";

// Sub-components (if needed for external use)
export { ConnectorCard } from "./components/connector-card";
export { DateRangeSelector } from "./components/date-range-selector";
export { PeriodicSyncConfig } from "./components/periodic-sync-config";
export { IndexingConfigurationView } from "./connector-configs/views/indexing-configuration-view";
export { ConnectorEditView } from "./connector-configs/views/connector-edit-view";
export { ConnectorDialogHeader } from "./components/connector-dialog-header";
export { AllConnectorsTab } from "./tabs/all-connectors-tab";
export { ActiveConnectorsTab } from "./tabs/active-connectors-tab";

// Constants and types
export { OAUTH_CONNECTORS, OTHER_CONNECTORS } from "./constants/connector-constants";
export type { IndexingConfigState } from "./constants/connector-constants";

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
} from "./constants/connector-popup.schemas";
export type {
	ConnectorPopupQueryParams,
	OAuthAuthResponse,
	FrequencyMinutes,
	DateRange,
} from "./constants/connector-popup.schemas";

// Hooks
export { useConnectorDialog } from "./hooks/use-connector-dialog";

