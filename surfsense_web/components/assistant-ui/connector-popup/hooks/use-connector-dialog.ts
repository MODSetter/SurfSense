import { format } from "date-fns";
import { useAtom, useAtomValue } from "jotai";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import {
	createConnectorMutationAtom,
	deleteConnectorMutationAtom,
	indexConnectorMutationAtom,
	updateConnectorMutationAtom,
} from "@/atoms/connectors/connector-mutation.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { searchSourceConnector } from "@/contracts/types/connector.types";
import { authenticatedFetch } from "@/lib/auth-utils";
import {
	trackConnectorConnected,
	trackConnectorDeleted,
	trackIndexWithDateRangeOpened,
	trackIndexWithDateRangeStarted,
	trackPeriodicIndexingStarted,
	trackQuickIndexClicked,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import type { IndexingConfigState } from "../constants/connector-constants";
import {
	AUTO_INDEX_CONNECTOR_TYPES,
	AUTO_INDEX_DEFAULTS,
	COMPOSIO_CONNECTORS,
	OAUTH_CONNECTORS,
	OTHER_CONNECTORS,
} from "../constants/connector-constants";
import {
	dateRangeSchema,
	frequencyMinutesSchema,
	parseOAuthAuthResponse,
	validateIndexingConfigState,
} from "../constants/connector-popup.schemas";

const OAUTH_RESULT_COOKIE = "connector_oauth_result";

function readOAuthResultCookie(): string | null {
	const match = document.cookie
		.split("; ")
		.find((row) => row.startsWith(`${OAUTH_RESULT_COOKIE}=`));
	return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

function clearOAuthResultCookie(): void {
	// biome-ignore lint: only standard way to expire a cookie
	document.cookie = `${OAUTH_RESULT_COOKIE}=; path=/; max-age=0`;
}

export const useConnectorDialog = () => {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { data: allConnectors, refetch: refetchAllConnectors } = useAtomValue(connectorsAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);
	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);
	const { mutateAsync: deleteConnector } = useAtomValue(deleteConnectorMutationAtom);
	const { mutateAsync: createConnector } = useAtomValue(createConnectorMutationAtom);

	// Use global atom for dialog open state so it can be controlled from anywhere
	const [isOpen, setIsOpen] = useAtom(connectorDialogOpenAtom);
	const [activeTab, setActiveTab] = useState("all");
	const [connectingId, setConnectingId] = useState<string | null>(null);
	const [isScrolled, setIsScrolled] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const [indexingConfig, setIndexingConfig] = useState<IndexingConfigState | null>(null);
	const [indexingConnector, setIndexingConnector] = useState<SearchSourceConnector | null>(null);
	const [indexingConnectorConfig, setIndexingConnectorConfig] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [isStartingIndexing, setIsStartingIndexing] = useState(false);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const [enableSummary, setEnableSummary] = useState(false);

	// Edit mode state
	const [editingConnector, setEditingConnector] = useState<SearchSourceConnector | null>(null);
	const [isSaving, setIsSaving] = useState(false);
	const [isDisconnecting, setIsDisconnecting] = useState(false);
	const [connectorConfig, setConnectorConfig] = useState<Record<string, unknown> | null>(null);
	const [connectorName, setConnectorName] = useState<string | null>(null);

	// Connect mode state (for non-OAuth connectors)
	const [connectingConnectorType, setConnectingConnectorType] = useState<string | null>(null);
	const [isCreatingConnector, setIsCreatingConnector] = useState(false);
	const isCreatingConnectorRef = useRef(false);
	const isAutoIndexingRef = useRef(false);

	// Accounts list view state (for OAuth connectors with multiple accounts)
	const [viewingAccountsType, setViewingAccountsType] = useState<{
		connectorType: string;
		connectorTitle: string;
	} | null>(null);

	// MCP list view state (for managing multiple MCP connectors)
	const [viewingMCPList, setViewingMCPList] = useState(false);

	// Track if we came from accounts list when entering edit mode
	const [cameFromAccountsList, setCameFromAccountsList] = useState<{
		connectorType: string;
		connectorTitle: string;
	} | null>(null);

	// Track if we came from MCP list view when entering edit mode
	const [cameFromMCPList, setCameFromMCPList] = useState(false);

	// Track if we came from MCP list view when entering connect mode
	const [connectCameFromMCPList, setConnectCameFromMCPList] = useState(false);

	// Helper function to get frequency label
	const getFrequencyLabel = useCallback((minutes: string): string => {
		switch (minutes) {
			case "15":
				return "15 minutes";
			case "60":
				return "hour";
			case "360":
				return "6 hours";
			case "720":
				return "12 hours";
			case "1440":
				return "day";
			case "10080":
				return "week";
			default:
				return `${minutes} minutes`;
		}
	}, []);

	const handleAutoIndex = useCallback(
		async (connector: SearchSourceConnector, connectorTitle: string, connectorType: string) => {
			if (!searchSpaceId || isAutoIndexingRef.current) return;
			isAutoIndexingRef.current = true;

			const defaults = AUTO_INDEX_DEFAULTS[connectorType];
			const now = new Date();
			const startDate = new Date(now);
			startDate.setDate(startDate.getDate() - (defaults?.daysBack ?? 365));
			const endDate = new Date(now);
			endDate.setDate(endDate.getDate() + (defaults?.daysForward ?? 0));

			const toastId = "auto-index";
			toast.loading(`Setting up ${connectorTitle}...`, { id: toastId });

			try {
				await updateConnector({
					id: connector.id,
					data: {
						periodic_indexing_enabled: true,
						indexing_frequency_minutes: defaults?.frequencyMinutes ?? 1440,
					},
				});

				await indexConnector({
					connector_id: connector.id,
					queryParams: {
						search_space_id: searchSpaceId,
						start_date: format(startDate, "yyyy-MM-dd"),
						end_date: format(endDate, "yyyy-MM-dd"),
					},
				});

				trackIndexWithDateRangeStarted(Number(searchSpaceId), connectorType, connector.id, {
					hasStartDate: true,
					hasEndDate: true,
				});

				toast.success(`${connectorTitle} connected!`, {
					id: toastId,
					description: defaults?.syncDescription ?? "Syncing started.",
				});
			} catch (error) {
				console.error("Auto-index failed:", error);
				toast.error(`${connectorTitle} connected, but sync failed`, {
					id: toastId,
					description: "You can start syncing from settings.",
				});
			} finally {
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
				});
				await refetchAllConnectors();
				isAutoIndexingRef.current = false;
			}
		},
		[searchSpaceId, indexConnector, updateConnector, refetchAllConnectors]
	);

	// YouTube view state
	const [isYouTubeView, setIsYouTubeView] = useState(false);

	// Track whether the current indexing config came from an OAuth redirect
	const [isFromOAuth, setIsFromOAuth] = useState(false);

	// Consume OAuth result from cookie (set by /connectors/callback route handler)
	useEffect(() => {
		const raw = readOAuthResultCookie();
		if (!raw || !searchSpaceId) return;
		clearOAuthResultCookie();

		let result: {
			success: string | null;
			error: string | null;
			connector: string | null;
			connectorId: string | null;
		};
		try {
			result = JSON.parse(raw);
		} catch {
			return;
		}

		if (result.error) {
			const oauthConnector = result.connector
				? OAUTH_CONNECTORS.find((c) => c.id === result.connector)
				: null;
			const name = oauthConnector?.title || "connector";

			if (result.error === "duplicate_account") {
				toast.error(`This ${name} account is already connected`, {
					description: "Please use a different account or manage the existing connection.",
				});
			} else {
				toast.error(`Failed to connect ${name}`, {
					description: result.error.replace(/_/g, " "),
				});
			}

			setIsOpen(true);
			return;
		}

		if (result.success === "true") {
			const earlyConnector = result.connector
				? OAUTH_CONNECTORS.find((c) => c.id === result.connector) ||
					COMPOSIO_CONNECTORS.find((c) => c.id === result.connector)
				: null;

			if (earlyConnector && AUTO_INDEX_CONNECTOR_TYPES.has(earlyConnector.connectorType)) {
				toast.loading(`Setting up ${earlyConnector.title}...`, { id: "auto-index" });
				setIsOpen(false);
			}

			refetchAllConnectors().then(async (fetchResult) => {
				if (!fetchResult.data) {
					toast.dismiss("auto-index");
					return;
				}

				let newConnector: SearchSourceConnector | undefined;
				let oauthConnector:
					| (typeof OAUTH_CONNECTORS)[number]
					| (typeof COMPOSIO_CONNECTORS)[number]
					| undefined;

				if (result.connectorId) {
					const connectorId = parseInt(result.connectorId, 10);
					newConnector = fetchResult.data.find((c: SearchSourceConnector) => c.id === connectorId);
					if (newConnector) {
						const connectorType = newConnector.connector_type;
						oauthConnector =
							OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
							COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);
					}
				}

				if (!newConnector && result.connector) {
					oauthConnector =
						OAUTH_CONNECTORS.find((c) => c.id === result.connector) ||
						COMPOSIO_CONNECTORS.find((c) => c.id === result.connector);
					if (oauthConnector) {
						const oauthType = oauthConnector.connectorType;
						newConnector = fetchResult.data.find(
							(c: SearchSourceConnector) => c.connector_type === oauthType
						);
					}
				}

				if (newConnector && oauthConnector) {
					const connectorValidation = searchSourceConnector.safeParse(newConnector);
					if (connectorValidation.success) {
						trackConnectorConnected(
							Number(searchSpaceId),
							oauthConnector.connectorType,
							newConnector.id
						);

						if (
							newConnector.is_indexable &&
							AUTO_INDEX_CONNECTOR_TYPES.has(oauthConnector.connectorType)
						) {
							await handleAutoIndex(
								newConnector,
								oauthConnector.title,
								oauthConnector.connectorType
							);
						} else {
							toast.dismiss("auto-index");
							const config = validateIndexingConfigState({
								connectorType: oauthConnector.connectorType,
								connectorId: newConnector.id,
								connectorTitle: oauthConnector.title,
							});
							setIndexingConfig(config);
							setIndexingConnector(newConnector);
							setIndexingConnectorConfig(newConnector.config);
							setIsFromOAuth(true);
							setIsOpen(true);
						}
					} else {
						console.warn("Invalid connector data after OAuth:", connectorValidation.error);
						toast.dismiss("auto-index");
						toast.error("Failed to validate connector data");
					}
				} else {
					toast.dismiss("auto-index");
				}
			});
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [searchSpaceId, handleAutoIndex, refetchAllConnectors, setIsOpen]);

	// Handle OAuth connection
	const handleConnectOAuth = useCallback(
		async (connector: (typeof OAUTH_CONNECTORS)[number] | (typeof COMPOSIO_CONNECTORS)[number]) => {
			if (!searchSpaceId || !connector.authEndpoint) return;

			// Set connecting state immediately to disable button and show spinner
			setConnectingId(connector.id);

			try {
				// Check if authEndpoint already has query parameters
				const separator = connector.authEndpoint.includes("?") ? "&" : "?";
				const url = `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}${connector.authEndpoint}${separator}space_id=${searchSpaceId}`;

				const response = await authenticatedFetch(url, { method: "GET" });

				if (!response.ok) {
					throw new Error(`Failed to initiate ${connector.title} OAuth`);
				}

				const data = await response.json();

				// Validate OAuth response with Zod
				const validatedData = parseOAuthAuthResponse(data);

				// Don't clear connectingId here - let the redirect happen with button still disabled
				// The component will unmount on redirect anyway
				window.location.href = validatedData.auth_url;
			} catch (error) {
				console.error(`Error connecting to ${connector.title}:`, error);
				if (error instanceof Error && error.message.includes("Invalid auth URL")) {
					toast.error(`Invalid response from ${connector.title} OAuth endpoint`);
				} else {
					toast.error(`Failed to connect to ${connector.title}`);
				}
				// Only clear connectingId on error so user can retry
				setConnectingId(null);
			}
		},
		[searchSpaceId]
	);

	// Handle creating YouTube crawler (not a connector, shows view in popup)
	const handleCreateYouTubeCrawler = useCallback(() => {
		if (!searchSpaceId) return;
		setIsYouTubeView(true);
	}, [searchSpaceId]);

	// Handle creating webcrawler connector
	const handleCreateWebcrawler = useCallback(async () => {
		if (!searchSpaceId) return;

		setConnectingId("webcrawler-connector");
		try {
			await createConnector({
				data: {
					name: "Web Pages",
					connector_type: EnumConnectorName.WEBCRAWLER_CONNECTOR,
					config: {},
					is_indexable: true,
					is_active: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
					enable_summary: false,
				},
				queryParams: {
					search_space_id: searchSpaceId,
				},
			});

			// Refetch connectors to get the new one
			const result = await refetchAllConnectors();
			if (result.data) {
				const connector = result.data.find(
					(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.WEBCRAWLER_CONNECTOR
				);
				if (connector) {
					const connectorValidation = searchSourceConnector.safeParse(connector);
					if (connectorValidation.success) {
						// Track webcrawler connector connected
						trackConnectorConnected(
							Number(searchSpaceId),
							EnumConnectorName.WEBCRAWLER_CONNECTOR,
							connector.id
						);

						const config = validateIndexingConfigState({
							connectorType: EnumConnectorName.WEBCRAWLER_CONNECTOR,
							connectorId: connector.id,
							connectorTitle: "Web Pages",
						});
						setIndexingConfig(config);
						setIndexingConnector(connector);
						setIndexingConnectorConfig(connector.config || {});
						setIsOpen(true);
					}
				}
			}
		} catch (error) {
			console.error("Error creating webcrawler connector:", error);
			toast.error("Failed to create web crawler connector");
		} finally {
			setConnectingId(null);
		}
	}, [searchSpaceId, createConnector, refetchAllConnectors, setIsOpen]);

	// Handle connecting non-OAuth connectors (like Tavily API)
	const handleConnectNonOAuth = useCallback(
		(connectorType: string) => {
			if (!searchSpaceId) return;
			setConnectingConnectorType(connectorType);
		},
		[searchSpaceId]
	);

	// Handle submitting connect form
	const handleSubmitConnectForm = useCallback(
		async (
			formData: {
				name: string;
				connector_type: string;
				config: Record<string, unknown>;
				is_indexable: boolean;
				last_indexed_at: null;
				periodic_indexing_enabled: boolean;
				indexing_frequency_minutes: number | null;
				next_scheduled_at: null;
				startDate?: Date;
				endDate?: Date;
				periodicEnabled?: boolean;
				frequencyMinutes?: string;
			},
			onIndexingStart?: (connectorId: number) => void
		) => {
			if (!searchSpaceId || !connectingConnectorType) {
				return;
			}

			// Prevent multiple submissions using ref for immediate check
			if (isCreatingConnectorRef.current) return;
			isCreatingConnectorRef.current = true;

			setIsCreatingConnector(true);
			try {
				// Extract UI-only fields before sending to backend
				const { startDate, endDate, periodicEnabled, frequencyMinutes, ...connectorData } =
					formData;

				// Create connector - ensure types match the schema
				const newConnector = await createConnector({
					data: {
						...connectorData,
						connector_type: connectorData.connector_type as EnumConnectorName,
						is_active: true,
						next_scheduled_at: connectorData.next_scheduled_at as string | null,
						enable_summary: false,
					},
					queryParams: {
						search_space_id: searchSpaceId,
					},
				});
				// Refetch connectors to get the new one
				const result = await refetchAllConnectors();
				if (result.data) {
					const connector = result.data.find(
						(c: SearchSourceConnector) => c.id === newConnector.id
					);
					if (connector) {
						// Validate connector data
						const connectorValidation = searchSourceConnector.safeParse(connector);
						if (connectorValidation.success) {
							// Store connectingConnectorType before clearing it
							const currentConnectorType = connectingConnectorType;

							// Track connector connected event for non-OAuth connectors
							trackConnectorConnected(Number(searchSpaceId), currentConnectorType, connector.id);

							// Find connector title from constants
							const connectorInfo = OTHER_CONNECTORS.find(
								(c) => c.connectorType === currentConnectorType
							);
							const connectorTitle = connectorInfo?.title || connector.name;

							// Set up indexing config
							const config = validateIndexingConfigState({
								connectorType: currentConnectorType as EnumConnectorName,
								connectorId: connector.id,
								connectorTitle,
							});

							// Clear connecting state to allow view transition
							setConnectingConnectorType(null);

							// Set indexing config state
							setIndexingConfig(config);
							setIndexingConnector(connector);
							setIndexingConnectorConfig(connector.config || {});

							// Pre-populate indexing configuration with values from form if provided
							if (formData.startDate !== undefined) {
								setStartDate(formData.startDate);
							}
							if (formData.endDate !== undefined) {
								setEndDate(formData.endDate);
							}
							if (formData.periodicEnabled !== undefined) {
								setPeriodicEnabled(formData.periodicEnabled);
							}
							if (formData.frequencyMinutes !== undefined) {
								setFrequencyMinutes(formData.frequencyMinutes);
							}

							// Auto-start indexing for non-OAuth reindexable connectors
							// This only applies to non-OAuth reindexable connectors (e.g., Elasticsearch)
							// Non-reindexable connectors (e.g., Tavily) have is_indexable: false, so they won't trigger this
							// Backend will use default date ranges (365 days ago to today) if dates are not provided
							if (connector.is_indexable) {
								// Get indexing configuration from form (or use defaults)
								const startDateForIndexing = formData.startDate;
								const endDateForIndexing = formData.endDate;
								const periodicEnabledForIndexing = formData.periodicEnabled || false;
								const frequencyMinutesForIndexing = formData.frequencyMinutes || "1440";

								// Update connector with periodic sync settings if enabled
								if (periodicEnabledForIndexing) {
									const frequency = parseInt(frequencyMinutesForIndexing, 10);
									await updateConnector({
										id: connector.id,
										data: {
											periodic_indexing_enabled: true,
											indexing_frequency_minutes: frequency,
										},
									});
								}

								// Notify caller that indexing is starting (for UI syncing state)
								if (onIndexingStart) {
									onIndexingStart(connector.id);
								}

								// Start indexing (backend will use defaults if dates are undefined)
								const startDateStr = startDateForIndexing
									? format(startDateForIndexing, "yyyy-MM-dd")
									: undefined;
								const endDateStr = endDateForIndexing
									? format(endDateForIndexing, "yyyy-MM-dd")
									: undefined;

								await indexConnector({
									connector_id: connector.id,
									queryParams: {
										search_space_id: searchSpaceId,
										start_date: startDateStr,
										end_date: endDateStr,
									},
								});

								const successMessage =
									currentConnectorType === "MCP_CONNECTOR"
										? `${connector.name} added successfully`
										: `${connectorTitle} connected and syncing started!`;
								toast.success(successMessage);

								setIsOpen(false);

								setIndexingConfig(null);
								setIndexingConnector(null);
								setIndexingConnectorConfig(null);

								queryClient.invalidateQueries({
									queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
								});

								await refetchAllConnectors();
							} else {
								// Non-indexable connector
								// For Circleback, transition to edit view to show webhook URL
								// For other non-indexable connectors, just close the modal
								if (currentConnectorType === "CIRCLEBACK_CONNECTOR") {
									// Clear connecting state and indexing config state
									setConnectingConnectorType(null);
									setIndexingConfig(null);
									setIndexingConnector(null);
									setIndexingConnectorConfig(null);

									// Set up edit view state
									setEditingConnector(connector);
									setConnectorName(connector.name);
									setConnectorConfig(connector.config || {});
									setPeriodicEnabled(false);
									setFrequencyMinutes("1440");
									setEnableSummary(connector.enable_summary ?? false);
									setStartDate(undefined);
									setEndDate(undefined);

									toast.success(`${connectorTitle} connected successfully!`, {
										description: "Configure the webhook URL in your Circleback settings.",
									});

									await refetchAllConnectors();
								} else {
									// Other non-indexable connectors - just show success message and close
									const successMessage =
										currentConnectorType === "MCP_CONNECTOR"
											? `${connector.name} added successfully`
											: `${connectorTitle} connected successfully!`;
									toast.success(successMessage);

									await refetchAllConnectors();

									setIsOpen(false);

									setIndexingConfig(null);
									setIndexingConnector(null);
									setIndexingConnectorConfig(null);
								}
							}
						}
					}
				}
			} catch (error) {
				console.error("Error creating connector:", error);
				toast.error(error instanceof Error ? error.message : "Failed to create connector");
			} finally {
				isCreatingConnectorRef.current = false;
				setIsCreatingConnector(false);
				// Don't clear connectingConnectorType here - it's cleared above when transitioning to config view
			}
		},
		[
			connectingConnectorType,
			searchSpaceId,
			createConnector,
			refetchAllConnectors,
			updateConnector,
			indexConnector,
			setIsOpen,
		]
	);

	// Handle going back from connect view
	const handleBackFromConnect = useCallback(() => {
		if (connectCameFromMCPList) {
			setViewingMCPList(true);
			setConnectCameFromMCPList(false);
		}
		setConnectingConnectorType(null);
	}, [connectCameFromMCPList]);

	// Handle going back from YouTube view
	const handleBackFromYouTube = useCallback(() => {
		setIsYouTubeView(false);
	}, []);

	// Handle viewing accounts list for OAuth connector type
	const handleViewAccountsList = useCallback(
		(connectorType: string, _connectorTitle?: string) => {
			if (!searchSpaceId) return;

			const oauthConnector =
				OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
				COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);
			if (oauthConnector) {
				setViewingAccountsType({
					connectorType: oauthConnector.connectorType,
					connectorTitle: oauthConnector.title,
				});
			}
		},
		[searchSpaceId]
	);

	// Handle going back from accounts list view
	const handleBackFromAccountsList = useCallback(() => {
		setViewingAccountsType(null);
	}, []);

	// Handle viewing MCP list
	const handleViewMCPList = useCallback(() => {
		if (!searchSpaceId) return;
		setViewingMCPList(true);
	}, [searchSpaceId]);

	// Handle going back from MCP list view
	const handleBackFromMCPList = useCallback(() => {
		setViewingMCPList(false);
	}, []);

	// Handle adding new MCP from list view
	const handleAddNewMCPFromList = useCallback(() => {
		setConnectCameFromMCPList(true);
		setViewingMCPList(false);
		setConnectingConnectorType("MCP_CONNECTOR");
	}, []);

	// Handle starting indexing
	const handleStartIndexing = useCallback(
		async (refreshConnectors: () => void) => {
			if (!indexingConfig || !searchSpaceId) return;

			// Validate date range (skip for Google Drive, Composio Drive, and Webcrawler)
			if (
				indexingConfig.connectorType !== "GOOGLE_DRIVE_CONNECTOR" &&
				indexingConfig.connectorType !== "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" &&
				indexingConfig.connectorType !== "WEBCRAWLER_CONNECTOR"
			) {
				const dateRangeValidation = dateRangeSchema.safeParse({ startDate, endDate });
				if (!dateRangeValidation.success) {
					const firstIssueMsg =
						dateRangeValidation.error.issues && dateRangeValidation.error.issues.length > 0
							? dateRangeValidation.error.issues[0].message
							: "Invalid date range";
					toast.error(firstIssueMsg);
					return;
				}
			}

			// Validate frequency minutes if periodic is enabled
			if (periodicEnabled) {
				const frequencyValidation = frequencyMinutesSchema.safeParse(frequencyMinutes);
				if (!frequencyValidation.success) {
					toast.error("Invalid frequency value");
					return;
				}
			}

			setIsStartingIndexing(true);
			try {
				const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
				const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

				// Update connector with summary, periodic sync settings, and config changes
				if (enableSummary || periodicEnabled || indexingConnectorConfig) {
					const frequency = periodicEnabled ? parseInt(frequencyMinutes, 10) : undefined;
					await updateConnector({
						id: indexingConfig.connectorId,
						data: {
							enable_summary: enableSummary,
							...(periodicEnabled && {
								periodic_indexing_enabled: true,
								indexing_frequency_minutes: frequency,
							}),
							...(indexingConnectorConfig && {
								config: indexingConnectorConfig,
							}),
						},
					});
				}

				// Handle Google Drive folder selection (regular and Composio)
				if (
					(indexingConfig.connectorType === "GOOGLE_DRIVE_CONNECTOR" ||
						indexingConfig.connectorType === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR") &&
					indexingConnectorConfig
				) {
					const selectedFolders = indexingConnectorConfig.selected_folders as
						| Array<{ id: string; name: string }>
						| undefined;
					const selectedFiles = indexingConnectorConfig.selected_files as
						| Array<{ id: string; name: string }>
						| undefined;
					const indexingOptions = indexingConnectorConfig.indexing_options as
						| {
								max_files_per_folder: number;
								incremental_sync: boolean;
								include_subfolders: boolean;
						  }
						| undefined;
					if (
						(selectedFolders && selectedFolders.length > 0) ||
						(selectedFiles && selectedFiles.length > 0)
					) {
						// Index with folder/file selection and indexing options
						await indexConnector({
							connector_id: indexingConfig.connectorId,
							queryParams: {
								search_space_id: searchSpaceId,
							},
							body: {
								folders: selectedFolders || [],
								files: selectedFiles || [],
								indexing_options: indexingOptions || {
									max_files_per_folder: 100,
									incremental_sync: true,
									include_subfolders: true,
								},
							},
						});
					} else {
						// Google Drive requires folder selection - show error if none selected
						toast.error("Please select at least one folder to index");
						setIsStartingIndexing(false);
						return;
					}
				} else if (indexingConfig.connectorType === "WEBCRAWLER_CONNECTOR") {
					// Webcrawler doesn't use date ranges, just uses config (API key and URLs)
					await indexConnector({
						connector_id: indexingConfig.connectorId,
						queryParams: {
							search_space_id: searchSpaceId,
						},
					});
				} else {
					await indexConnector({
						connector_id: indexingConfig.connectorId,
						queryParams: {
							search_space_id: searchSpaceId,
							start_date: startDateStr,
							end_date: endDateStr,
						},
					});
				}

				// Track index with date range started event
				trackIndexWithDateRangeStarted(
					Number(searchSpaceId),
					indexingConfig.connectorType,
					indexingConfig.connectorId,
					{
						hasStartDate: !!startDate,
						hasEndDate: !!endDate,
					}
				);

				// Track periodic indexing started if enabled
				if (periodicEnabled) {
					trackPeriodicIndexingStarted(
						Number(searchSpaceId),
						indexingConfig.connectorType,
						indexingConfig.connectorId,
						parseInt(frequencyMinutes, 10)
					);
				}

				toast.success(`${indexingConfig.connectorTitle} indexing started`);

				setIsOpen(false);
				setIsFromOAuth(false);
				setIndexingConfig(null);
				setIndexingConnector(null);
				setIndexingConnectorConfig(null);

				refreshConnectors();
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
				});
			} catch (error) {
				console.error("Error starting indexing:", error);
				toast.error("Failed to start indexing");
			} finally {
				setIsStartingIndexing(false);
			}
		},
		[
			indexingConfig,
			searchSpaceId,
			startDate,
			endDate,
			indexConnector,
			updateConnector,
			periodicEnabled,
			frequencyMinutes,
			enableSummary,
			indexingConnectorConfig,
			setIsOpen,
		]
	);

	// Handle skipping indexing
	const handleSkipIndexing = useCallback(() => {
		setIsOpen(false);
		setIsFromOAuth(false);
		setIndexingConfig(null);
		setIndexingConnector(null);
		setIndexingConnectorConfig(null);
	}, [setIsOpen]);

	// Handle starting edit mode
	const handleStartEdit = useCallback(
		(connector: SearchSourceConnector) => {
			if (!searchSpaceId) return;

			// For MCP connectors from "All Connectors" tab, show the list view instead of directly editing
			// (unless we're already in the MCP list view or on the Active tab where individual MCPs are shown)
			if (connector.connector_type === "MCP_CONNECTOR" && !viewingMCPList && activeTab === "all") {
				handleViewMCPList();
				return;
			}

			// All connector types should be handled in the popup edit view
			// Validate connector data
			const connectorValidation = searchSourceConnector.safeParse(connector);
			if (!connectorValidation.success) {
				toast.error("Invalid connector data");
				return;
			}

			// Track if we came from accounts list view so handleBackFromEdit can restore it
			if (viewingAccountsType && viewingAccountsType.connectorType === connector.connector_type) {
				setCameFromAccountsList(viewingAccountsType);
			} else {
				setCameFromAccountsList(null);
			}
			setViewingAccountsType(null);

			// Track if we came from MCP list view so handleBackFromEdit can restore it
			if (viewingMCPList && connector.connector_type === "MCP_CONNECTOR") {
				setCameFromMCPList(true);
			} else {
				setCameFromMCPList(false);
			}
			setViewingMCPList(false);

			// Track index with date range opened event
			if (connector.is_indexable) {
				trackIndexWithDateRangeOpened(
					Number(searchSpaceId),
					connector.connector_type,
					connector.id
				);
			}

			setEditingConnector(connector);
			setConnectorName(connector.name);
			setPeriodicEnabled(!connector.is_indexable ? false : connector.periodic_indexing_enabled);
			setFrequencyMinutes(connector.indexing_frequency_minutes?.toString() || "1440");
			setEnableSummary(connector.enable_summary ?? false);
			setStartDate(undefined);
			setEndDate(undefined);
		},
		[searchSpaceId, viewingAccountsType, viewingMCPList, handleViewMCPList, activeTab]
	);

	// Handle saving connector changes
	const handleSaveConnector = useCallback(
		async (refreshConnectors: () => void) => {
			if (!editingConnector || !searchSpaceId || isSaving) return;

			// Validate date range (skip for Google Drive which uses folder selection, Webcrawler which uses config, and non-indexable connectors)
			if (
				editingConnector.is_indexable &&
				editingConnector.connector_type !== "GOOGLE_DRIVE_CONNECTOR" &&
				editingConnector.connector_type !== "WEBCRAWLER_CONNECTOR"
			) {
				const dateRangeValidation = dateRangeSchema.safeParse({ startDate, endDate });
				if (!dateRangeValidation.success) {
					toast.error(dateRangeValidation.error.issues[0]?.message || "Invalid date range");
					return;
				}
			}

			// Prevent periodic indexing for non-indexable connectors
			if (periodicEnabled && !editingConnector.is_indexable) {
				toast.error("Periodic indexing is not available for this connector type");
				return;
			}

			// Prevent periodic indexing for Google Drive (regular or Composio) without folders/files selected
			if (
				periodicEnabled &&
				(editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ||
					editingConnector.connector_type === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR")
			) {
				const selectedFolders = (connectorConfig || editingConnector.config)?.selected_folders as
					| Array<{ id: string; name: string }>
					| undefined;
				const selectedFiles = (connectorConfig || editingConnector.config)?.selected_files as
					| Array<{ id: string; name: string }>
					| undefined;
				const hasItemsSelected =
					(selectedFolders && selectedFolders.length > 0) ||
					(selectedFiles && selectedFiles.length > 0);

				if (!hasItemsSelected) {
					toast.error("Select at least one folder or file to enable periodic sync");
					return;
				}
			}

			// Validate frequency minutes if periodic is enabled (only for indexable connectors)
			if (periodicEnabled && editingConnector.is_indexable) {
				const frequencyValidation = frequencyMinutesSchema.safeParse(frequencyMinutes);
				if (!frequencyValidation.success) {
					toast.error("Invalid frequency value");
					return;
				}
			}

			setIsSaving(true);
			try {
				const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
				const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

				// Update connector with periodic sync settings, config changes, and name
				const frequency =
					periodicEnabled && editingConnector.is_indexable ? parseInt(frequencyMinutes, 10) : null;
				await updateConnector({
					id: editingConnector.id,
					data: {
						name: connectorName || editingConnector.name,
						enable_summary: enableSummary,
						periodic_indexing_enabled: !editingConnector.is_indexable ? false : periodicEnabled,
						indexing_frequency_minutes: !editingConnector.is_indexable ? null : frequency,
						config: connectorConfig || editingConnector.config,
					},
				});

				// Re-index based on connector type (only for indexable connectors)
				let indexingDescription = "Settings saved.";
				if (!editingConnector.is_indexable) {
					// Non-indexable connectors (like Tavily API) don't need re-indexing
					indexingDescription = "Settings saved.";
				} else if (
					editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ||
					editingConnector.connector_type === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"
				) {
					// Google Drive (both regular and Composio) uses folder selection from config, not date ranges
					const selectedFolders = (connectorConfig || editingConnector.config)?.selected_folders as
						| Array<{ id: string; name: string }>
						| undefined;
					const selectedFiles = (connectorConfig || editingConnector.config)?.selected_files as
						| Array<{ id: string; name: string }>
						| undefined;
					const indexingOptions = (connectorConfig || editingConnector.config)?.indexing_options as
						| {
								max_files_per_folder: number;
								incremental_sync: boolean;
								include_subfolders: boolean;
						  }
						| undefined;
					if (
						(selectedFolders && selectedFolders.length > 0) ||
						(selectedFiles && selectedFiles.length > 0)
					) {
						await indexConnector({
							connector_id: editingConnector.id,
							queryParams: {
								search_space_id: searchSpaceId,
							},
							body: {
								folders: selectedFolders || [],
								files: selectedFiles || [],
								indexing_options: indexingOptions || {
									max_files_per_folder: 100,
									incremental_sync: true,
									include_subfolders: true,
								},
							},
						});
						const totalItems = (selectedFolders?.length || 0) + (selectedFiles?.length || 0);
						indexingDescription = `Re-indexing started for ${totalItems} item(s).`;
					}
				} else if (editingConnector.connector_type === "WEBCRAWLER_CONNECTOR") {
					// Webcrawler uses config (API key and URLs), not date ranges
					await indexConnector({
						connector_id: editingConnector.id,
						queryParams: {
							search_space_id: searchSpaceId,
						},
					});
					indexingDescription = "Re-indexing started with updated configuration.";
				} else if (startDateStr || endDateStr) {
					// Other connectors use date ranges
					await indexConnector({
						connector_id: editingConnector.id,
						queryParams: {
							search_space_id: searchSpaceId,
							start_date: startDateStr,
							end_date: endDateStr,
						},
					});
					indexingDescription = "Re-indexing started with new date range.";
				}

				// Track indexing started if re-indexing was performed
				if (
					editingConnector.is_indexable &&
					(indexingDescription.includes("Re-indexing") || indexingDescription.includes("indexing"))
				) {
					trackIndexWithDateRangeStarted(
						Number(searchSpaceId),
						editingConnector.connector_type,
						editingConnector.id,
						{
							hasStartDate: !!startDateStr,
							hasEndDate: !!endDateStr,
						}
					);
				}

				// Track periodic indexing if enabled
				if (periodicEnabled && editingConnector.is_indexable) {
					trackPeriodicIndexingStarted(
						Number(searchSpaceId),
						editingConnector.connector_type,
						editingConnector.id,
						frequency || parseInt(frequencyMinutes, 10)
					);
				}

				// Generate toast message based on connector type
				const toastTitle = `${editingConnector.name} updated successfully`;

				toast.success(toastTitle, {
					description: periodicEnabled
						? `Periodic sync ${frequency ? `enabled every ${getFrequencyLabel(frequencyMinutes)}` : "enabled"}. ${indexingDescription}`
						: indexingDescription,
				});

				setIsOpen(false);

				refreshConnectors();
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
				});
			} catch (error) {
				console.error("Error saving connector:", error);
				toast.error("Failed to save connector changes");
			} finally {
				setIsSaving(false);
			}
		},
		[
			editingConnector,
			searchSpaceId,
			isSaving,
			startDate,
			endDate,
			indexConnector,
			updateConnector,
			periodicEnabled,
			frequencyMinutes,
			enableSummary,
			getFrequencyLabel,
			connectorConfig,
			connectorName,
			setIsOpen,
		]
	);

	// Handle disconnecting connector
	const handleDisconnectConnector = useCallback(
		async (refreshConnectors: () => void) => {
			if (!editingConnector || !searchSpaceId) return;

			setIsDisconnecting(true);
			try {
				await deleteConnector({
					id: editingConnector.id,
				});

				// Track connector deleted event
				trackConnectorDeleted(
					Number(searchSpaceId),
					editingConnector.connector_type,
					editingConnector.id
				);

				toast.success(
					editingConnector.connector_type === "MCP_CONNECTOR"
						? `${editingConnector.name} MCP server removed successfully`
						: `${editingConnector.name} disconnected successfully`
				);

				if (editingConnector.connector_type === "MCP_CONNECTOR" && cameFromMCPList) {
					setViewingMCPList(true);
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
				} else {
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
					setIsOpen(false);
				}

				refreshConnectors();
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
				});
			} catch (error) {
				console.error("Error disconnecting connector:", error);
				toast.error("Failed to disconnect connector");
			} finally {
				setIsDisconnecting(false);
			}
		},
		[editingConnector, searchSpaceId, deleteConnector, cameFromMCPList, setIsOpen]
	);

	// Handle quick index (index with selected date range, or backend defaults if none selected)
	const handleQuickIndexConnector = useCallback(
		async (
			connectorId: number,
			connectorType?: string,
			stopIndexing?: (id: number) => void,
			startDate?: Date,
			endDate?: Date
		) => {
			if (!searchSpaceId) {
				if (stopIndexing) {
					stopIndexing(connectorId);
				}
				return;
			}

			// Track quick index clicked event
			if (connectorType) {
				trackQuickIndexClicked(Number(searchSpaceId), connectorType, connectorId);
			}

			try {
				// Format dates if provided, otherwise pass undefined (backend will use defaults)
				const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
				const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

				await indexConnector({
					connector_id: connectorId,
					queryParams: {
						search_space_id: searchSpaceId,
						start_date: startDateStr,
						end_date: endDateStr,
					},
				});
				toast.success("Indexing started");

				// Invalidate queries to refresh data
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
				});
				// Note: Don't call stopIndexing here - let useIndexingConnectors hook
				// detect when last_indexed_at changes via real-time sync
			} catch (error) {
				console.error("Error indexing connector content:", error);
				toast.error(error instanceof Error ? error.message : "Failed to start indexing");
				// Stop indexing state on error
				if (stopIndexing) {
					stopIndexing(connectorId);
				}
			}
		},
		[searchSpaceId, indexConnector]
	);

	// Handle going back from edit view
	const handleBackFromEdit = useCallback(() => {
		if (editingConnector?.connector_type === "MCP_CONNECTOR" && cameFromMCPList) {
			setViewingMCPList(true);
			setCameFromMCPList(false);
			setEditingConnector(null);
			setConnectorName(null);
			setConnectorConfig(null);
			return;
		}

		if (cameFromAccountsList && editingConnector) {
			setViewingAccountsType(cameFromAccountsList);
			setCameFromAccountsList(null);
		}

		setEditingConnector(null);
		setConnectorName(null);
		setConnectorConfig(null);
	}, [cameFromAccountsList, editingConnector, cameFromMCPList]);

	// Handle dialog open/close
	const handleOpenChange = useCallback(
		(open: boolean) => {
			setIsOpen(open);

			if (!open) {
				setIsScrolled(false);
				setSearchQuery("");
				setIsYouTubeView(false);
				setIsFromOAuth(false);
				if (!isStartingIndexing && !isSaving && !isDisconnecting && !isCreatingConnector) {
					setIndexingConfig(null);
					setIndexingConnector(null);
					setIndexingConnectorConfig(null);
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
					setConnectingConnectorType(null);
					setViewingAccountsType(null);
					setViewingMCPList(false);
					setCameFromAccountsList(null);
					setCameFromMCPList(false);
					setConnectCameFromMCPList(false);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
					setEnableSummary(false);
				}
			}
		},
		[isStartingIndexing, isDisconnecting, isSaving, isCreatingConnector, setIsOpen]
	);

	const handleTabChange = useCallback((value: string) => {
		setActiveTab(value);
	}, []);

	// Handle scroll
	const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		setIsScrolled(e.currentTarget.scrollTop > 0);
	}, []);

	return {
		// State
		isOpen,
		activeTab,
		connectingId,
		isScrolled,
		searchQuery,
		indexingConfig,
		indexingConnector,
		indexingConnectorConfig,
		editingConnector,
		connectingConnectorType,
		isCreatingConnector,
		startDate,
		endDate,
		isStartingIndexing,
		isSaving,
		isDisconnecting,
		periodicEnabled,
		frequencyMinutes,
		enableSummary,
		searchSpaceId,
		allConnectors,
		viewingAccountsType,
		viewingMCPList,
		isYouTubeView,
		isFromOAuth,

		// Setters
		setSearchQuery,
		setStartDate,
		setEndDate,
		setPeriodicEnabled,
		setFrequencyMinutes,
		setEnableSummary,
		setConnectorName,

		// Handlers
		handleOpenChange,
		handleTabChange,
		handleScroll,
		handleConnectOAuth,
		handleConnectNonOAuth,
		handleCreateWebcrawler,
		handleCreateYouTubeCrawler,
		handleSubmitConnectForm,
		handleAutoIndex,
		handleStartIndexing,
		handleSkipIndexing,
		handleStartEdit,
		handleSaveConnector,
		handleDisconnectConnector,
		handleBackFromEdit,
		handleBackFromConnect,
		handleBackFromYouTube,
		handleViewAccountsList,
		handleBackFromAccountsList,
		handleViewMCPList,
		handleBackFromMCPList,
		handleAddNewMCPFromList,
		handleQuickIndexConnector,
		connectorConfig,
		setConnectorConfig,
		setIndexingConnectorConfig,
	};
};
