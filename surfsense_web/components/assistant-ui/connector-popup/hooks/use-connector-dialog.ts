import { format } from "date-fns";
import { useAtomValue } from "jotai";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
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
	COMPOSIO_CONNECTORS,
	OAUTH_CONNECTORS,
	OTHER_CONNECTORS,
} from "../constants/connector-constants";
import {
	dateRangeSchema,
	frequencyMinutesSchema,
	parseConnectorPopupQueryParams,
	parseOAuthAuthResponse,
	validateIndexingConfigState,
} from "../constants/connector-popup.schemas";

export const useConnectorDialog = () => {
	const router = useRouter();
	const searchParams = useSearchParams();
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { data: allConnectors, refetch: refetchAllConnectors } = useAtomValue(connectorsAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);
	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);
	const { mutateAsync: deleteConnector } = useAtomValue(deleteConnectorMutationAtom);
	const { mutateAsync: createConnector } = useAtomValue(createConnectorMutationAtom);

	const [isOpen, setIsOpen] = useState(false);
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

	// Synchronize state with URL query params
	useEffect(() => {
		try {
			const params = parseConnectorPopupQueryParams(searchParams);

			if (params.modal === "connectors") {
				setIsOpen(true);

				if (params.tab === "active" || params.tab === "all") {
					setActiveTab(params.tab);
				}

				// Clear indexing config if view is not "configure" anymore
				if (params.view !== "configure" && indexingConfig) {
					setIndexingConfig(null);
				}

				// Clear editing connector if view is not "edit" anymore
				if (params.view !== "edit" && editingConnector) {
					setEditingConnector(null);
					setConnectorName(null);
				}

				// Clear connecting connector type if view is not "connect" anymore
				if (params.view !== "connect" && connectingConnectorType) {
					setConnectingConnectorType(null);
				}

				// Clear viewing accounts type if view is not "accounts" anymore
				if (params.view !== "accounts" && viewingAccountsType) {
					setViewingAccountsType(null);
				}

				// Clear MCP list view if view is not "mcp-list" anymore
				if (params.view !== "mcp-list" && viewingMCPList) {
					setViewingMCPList(false);
				}

				// Handle MCP list view
				if (params.view === "mcp-list" && !viewingMCPList) {
					setViewingMCPList(true);
				}

				// Handle connect view
				if (params.view === "connect" && params.connectorType && !connectingConnectorType) {
					setConnectingConnectorType(params.connectorType);
				}

				// Handle accounts view
				if (params.view === "accounts" && params.connectorType) {
					// Update state if not set, or if connectorType has changed
					const needsUpdate =
						!viewingAccountsType || viewingAccountsType.connectorType !== params.connectorType;

					if (needsUpdate) {
						// Check both OAUTH_CONNECTORS and COMPOSIO_CONNECTORS
						const oauthConnector =
							OAUTH_CONNECTORS.find((c) => c.connectorType === params.connectorType) ||
							COMPOSIO_CONNECTORS.find((c) => c.connectorType === params.connectorType);
						if (oauthConnector) {
							setViewingAccountsType({
								connectorType: oauthConnector.connectorType,
								connectorTitle: oauthConnector.title,
							});
						}
					}
				}

				// Handle YouTube view
				if (params.view === "youtube") {
					// YouTube view is active - no additional state needed
				}

				// Handle configure view (for page refresh support)
				if (params.view === "configure" && params.connector && !indexingConfig && allConnectors) {
					// Check both OAUTH_CONNECTORS and COMPOSIO_CONNECTORS
					const oauthConnector =
						OAUTH_CONNECTORS.find((c) => c.id === params.connector) ||
						COMPOSIO_CONNECTORS.find((c) => c.id === params.connector);
					if (oauthConnector) {
						let existingConnector: SearchSourceConnector | undefined;
						if (params.connectorId) {
							const connectorId = parseInt(params.connectorId, 10);
							existingConnector = allConnectors.find(
								(c: SearchSourceConnector) => c.id === connectorId
							);
						} else {
							existingConnector = allConnectors.find(
								(c: SearchSourceConnector) => c.connector_type === oauthConnector.connectorType
							);
						}
						if (existingConnector) {
							const connectorValidation = searchSourceConnector.safeParse(existingConnector);
							if (connectorValidation.success) {
								const config = validateIndexingConfigState({
									connectorType: oauthConnector.connectorType,
									connectorId: existingConnector.id,
									connectorTitle: oauthConnector.title,
								});
								setIndexingConfig(config);
								setIndexingConnector(existingConnector);
								setIndexingConnectorConfig(existingConnector.config);
							}
						}
					}
				}

				// Handle edit view
				if (params.view === "edit" && params.connectorId && allConnectors && !editingConnector) {
					const connectorId = parseInt(params.connectorId, 10);
					const connector = allConnectors.find((c: SearchSourceConnector) => c.id === connectorId);
					if (connector) {
						const connectorValidation = searchSourceConnector.safeParse(connector);
						if (connectorValidation.success) {
							setEditingConnector(connector);
							setConnectorConfig(connector.config);
							setConnectorName(connector.name);
							// Load existing periodic sync settings (disabled for non-indexable connectors)
							setPeriodicEnabled(
								!connector.is_indexable ? false : connector.periodic_indexing_enabled
							);
							setFrequencyMinutes(connector.indexing_frequency_minutes?.toString() || "1440");
							// Reset dates - user can set new ones for re-indexing
							setStartDate(undefined);
							setEndDate(undefined);
						}
					}
				}
			} else {
				setIsOpen(false);
				// Clear indexing config when modal is closed
				if (indexingConfig) {
					setIndexingConfig(null);
					setIndexingConnector(null);
					setIndexingConnectorConfig(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
					setIsScrolled(false);
					setSearchQuery("");
				}
				// Clear editing connector when modal is closed
				if (editingConnector) {
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
					setIsScrolled(false);
					setSearchQuery("");
				}
				// Clear connecting connector type when modal is closed
				if (connectingConnectorType) {
					setConnectingConnectorType(null);
				}
				// Clear viewing accounts type when modal is closed
				if (viewingAccountsType) {
					setViewingAccountsType(null);
				}
				// Clear YouTube view when modal is closed (handled by view param check)
			}
		} catch (error) {
			// Invalid query params - log but don't crash
			console.warn("Invalid connector popup query params:", error);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [
		searchParams,
		allConnectors,
		editingConnector,
		indexingConfig,
		connectingConnectorType,
		viewingAccountsType,
		viewingMCPList,
	]);

	// Detect OAuth success / Failure and transition to config view
	useEffect(() => {
		try {
			const params = parseConnectorPopupQueryParams(searchParams);

			// Handle OAuth errors (e.g., duplicate account)
			if (params.error && params.modal === "connectors") {
				const oauthConnector = params.connector
					? OAUTH_CONNECTORS.find((c) => c.id === params.connector)
					: null;
				const connectorName = oauthConnector?.title || "connector";

				if (params.error === "duplicate_account") {
					toast.error(`This ${connectorName} account is already connected`, {
						description: "Please use a different account or manage the existing connection.",
					});
				} else {
					toast.error(`Failed to connect ${connectorName}`, {
						description: params.error.replace(/_/g, " "),
					});
				}

				// Clean up error params from URL
				const url = new URL(window.location.href);
				url.searchParams.delete("error");
				url.searchParams.delete("connector");
				window.history.replaceState({}, "", url.toString());

				// Open the popup to show the connectors
				setIsOpen(true);
				return;
			}

			if (params.success === "true" && searchSpaceId && params.modal === "connectors") {
				refetchAllConnectors().then((result) => {
					if (!result.data) return;

					let newConnector: SearchSourceConnector | undefined;
					let oauthConnector:
						| (typeof OAUTH_CONNECTORS)[number]
						| (typeof COMPOSIO_CONNECTORS)[number]
						| undefined;

					// First, try to find connector by connectorId if provided
					if (params.connectorId) {
						const connectorId = parseInt(params.connectorId, 10);
						newConnector = result.data.find((c: SearchSourceConnector) => c.id === connectorId);

						// If we found the connector, find the matching OAuth/Composio connector by type
						if (newConnector) {
							oauthConnector =
								OAUTH_CONNECTORS.find((c) => c.connectorType === newConnector!.connector_type) ||
								COMPOSIO_CONNECTORS.find((c) => c.connectorType === newConnector!.connector_type);
						}
					}

					// If we don't have a connector yet, try to find by connector param
					if (!newConnector && params.connector) {
						oauthConnector =
							OAUTH_CONNECTORS.find((c) => c.id === params.connector) ||
							COMPOSIO_CONNECTORS.find((c) => c.id === params.connector);

						if (oauthConnector) {
							newConnector = result.data.find(
								(c: SearchSourceConnector) => c.connector_type === oauthConnector!.connectorType
							);
						}
					}

					if (newConnector && oauthConnector) {
						const connectorValidation = searchSourceConnector.safeParse(newConnector);
						if (connectorValidation.success) {
							// Track connector connected event for OAuth/Composio connectors
							trackConnectorConnected(
								Number(searchSpaceId),
								oauthConnector.connectorType,
								newConnector.id
							);

							const config = validateIndexingConfigState({
								connectorType: oauthConnector.connectorType,
								connectorId: newConnector.id,
								connectorTitle: oauthConnector.title,
							});
							setIndexingConfig(config);
							setIndexingConnector(newConnector);
							setIndexingConnectorConfig(newConnector.config);
							setIsOpen(true);
							const url = new URL(window.location.href);
							url.searchParams.delete("success");
							url.searchParams.set("connectorId", newConnector.id.toString());
							url.searchParams.set("view", "configure");
							window.history.replaceState({}, "", url.toString());
						} else {
							console.warn("Invalid connector data after OAuth:", connectorValidation.error);
							toast.error("Failed to validate connector data");
						}
					}
				});
			}
		} catch (error) {
			// Invalid query params - log but don't crash
			console.warn("Invalid connector popup query params in OAuth success handler:", error);
		}
	}, [searchParams, searchSpaceId, refetchAllConnectors]);

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

		// Update URL to show YouTube view
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("view", "youtube");
		window.history.pushState({ modal: true }, "", url.toString());
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
						const url = new URL(window.location.href);
						url.searchParams.set("modal", "connectors");
						url.searchParams.set("view", "configure");
						window.history.pushState({ modal: true }, "", url.toString());
					}
				}
			}
		} catch (error) {
			console.error("Error creating webcrawler connector:", error);
			toast.error("Failed to create web crawler connector");
		} finally {
			setConnectingId(null);
		}
	}, [searchSpaceId, createConnector, refetchAllConnectors]);

	// Handle connecting non-OAuth connectors (like Tavily API)
	const handleConnectNonOAuth = useCallback(
		(connectorType: string) => {
			if (!searchSpaceId) return;

			// Set connecting state
			setConnectingConnectorType(connectorType);

			// Update URL to show connect view
			const url = new URL(window.location.href);
			url.searchParams.set("modal", "connectors");
			url.searchParams.set("view", "connect");
			url.searchParams.set("connectorType", connectorType);
			window.history.pushState({ modal: true }, "", url.toString());
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
			if (!searchSpaceId || !connectingConnectorType) return;

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
										: `${connectorTitle} connected and indexing started!`;
								toast.success(successMessage, {
									description: periodicEnabledForIndexing
										? `Periodic sync enabled every ${getFrequencyLabel(frequencyMinutesForIndexing)}.`
										: "You can continue working while we sync your data.",
								});

								const url = new URL(window.location.href);
								url.searchParams.delete("modal");
								url.searchParams.delete("tab");
								url.searchParams.delete("view");
								url.searchParams.delete("connectorType");
								router.replace(url.pathname + url.search, { scroll: false });

								// Clear indexing config state since we're not showing the view
								setIndexingConfig(null);
								setIndexingConnector(null);
								setIndexingConnectorConfig(null);

								// Invalidate queries to refresh data
								queryClient.invalidateQueries({
									queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
								});

								// Refresh connectors list
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
									setStartDate(undefined);
									setEndDate(undefined);

									toast.success(`${connectorTitle} connected successfully!`, {
										description: "Configure the webhook URL in your Circleback settings.",
									});

									// Transition to edit view
									const url = new URL(window.location.href);
									url.searchParams.set("modal", "connectors");
									url.searchParams.set("view", "edit");
									url.searchParams.set("connectorId", connector.id.toString());
									url.searchParams.delete("connectorType");
									router.replace(url.pathname + url.search, { scroll: false });

									// Refresh connectors list
									await refetchAllConnectors();
								} else {
									// Other non-indexable connectors - just show success message and close
									const successMessage =
										currentConnectorType === "MCP_CONNECTOR"
											? `${connector.name} added successfully`
											: `${connectorTitle} connected successfully!`;
									toast.success(successMessage);

									// Refresh connectors list before closing modal
									await refetchAllConnectors();

									// Close modal and return to main view
									const url = new URL(window.location.href);
									url.searchParams.delete("modal");
									url.searchParams.delete("tab");
									url.searchParams.delete("view");
									url.searchParams.delete("connectorType");
									router.replace(url.pathname + url.search, { scroll: false });

									// Clear indexing config state
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
			router,
			getFrequencyLabel,
		]
	);

	// Handle going back from connect view
	const handleBackFromConnect = useCallback(() => {
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");

		// If we're connecting an MCP and came from list view, go back to list
		if (connectingConnectorType === "MCP_CONNECTOR" && viewingMCPList) {
			url.searchParams.set("view", "mcp-list");
		} else {
			url.searchParams.set("tab", "all");
			url.searchParams.delete("view");
		}

		url.searchParams.delete("connectorType");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router, connectingConnectorType, viewingMCPList]);

	// Handle going back from YouTube view
	const handleBackFromYouTube = useCallback(() => {
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("tab", "all");
		url.searchParams.delete("view");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

	// Handle viewing accounts list for OAuth connector type
	const handleViewAccountsList = useCallback(
		(connectorType: string, _connectorTitle?: string) => {
			if (!searchSpaceId) return;

			// Update URL to show accounts view, preserving current tab
			// The useEffect will handle setting viewingAccountsType based on URL params
			const url = new URL(window.location.href);
			url.searchParams.set("modal", "connectors");
			url.searchParams.set("view", "accounts");
			url.searchParams.set("connectorType", connectorType);
			// Keep the current tab in URL so we can go back to it
			router.replace(url.pathname + url.search, { scroll: false });
		},
		[searchSpaceId, router]
	);

	// Handle going back from accounts list view
	const handleBackFromAccountsList = useCallback(() => {
		setViewingAccountsType(null);
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		// Keep the current tab (don't change it) - just remove view-specific params
		url.searchParams.delete("view");
		url.searchParams.delete("connectorType");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

	// Handle viewing MCP list
	const handleViewMCPList = useCallback(() => {
		if (!searchSpaceId) return;

		setViewingMCPList(true);

		// Update URL to show MCP list view
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("view", "mcp-list");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [searchSpaceId, router]);

	// Handle going back from MCP list view
	const handleBackFromMCPList = useCallback(() => {
		setViewingMCPList(false);
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.delete("view");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

	// Handle adding new MCP from list view
	const handleAddNewMCPFromList = useCallback(() => {
		setConnectingConnectorType("MCP_CONNECTOR");
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("view", "connect");
		url.searchParams.set("connectorType", "MCP_CONNECTOR");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

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

				// Update connector with periodic sync settings and config changes
				if (periodicEnabled || indexingConnectorConfig) {
					const frequency = periodicEnabled ? parseInt(frequencyMinutes, 10) : undefined;
					await updateConnector({
						id: indexingConfig.connectorId,
						data: {
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

				toast.success(`${indexingConfig.connectorTitle} indexing started`, {
					description: periodicEnabled
						? `Periodic sync enabled every ${getFrequencyLabel(frequencyMinutes)}.`
						: "You can continue working while we sync your data.",
				});

				// Update URL - the effect will handle closing the modal and clearing state
				const url = new URL(window.location.href);
				url.searchParams.delete("modal");
				url.searchParams.delete("tab");
				url.searchParams.delete("success");
				url.searchParams.delete("connector");
				url.searchParams.delete("view");
				router.replace(url.pathname + url.search, { scroll: false });

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
			getFrequencyLabel,
			router,
			indexingConnectorConfig,
		]
	);

	// Handle skipping indexing
	const handleSkipIndexing = useCallback(() => {
		// Update URL - the effect will handle closing the modal and clearing state
		const url = new URL(window.location.href);
		url.searchParams.delete("modal");
		url.searchParams.delete("tab");
		url.searchParams.delete("success");
		url.searchParams.delete("connector");
		url.searchParams.delete("view");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

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

			// Track if we came from accounts list view
			// If viewingAccountsType matches this connector type, preserve it
			if (viewingAccountsType && viewingAccountsType.connectorType === connector.connector_type) {
				setCameFromAccountsList(viewingAccountsType);
			} else {
				setCameFromAccountsList(null);
			}

			// Track if we came from MCP list view
			if (viewingMCPList && connector.connector_type === "MCP_CONNECTOR") {
				setCameFromMCPList(true);
			} else {
				setCameFromMCPList(false);
			}

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
			// Load existing periodic sync settings (disabled for non-indexable connectors)
			setPeriodicEnabled(!connector.is_indexable ? false : connector.periodic_indexing_enabled);
			setFrequencyMinutes(connector.indexing_frequency_minutes?.toString() || "1440");
			// Reset dates - user can set new ones for re-indexing
			setStartDate(undefined);
			setEndDate(undefined);

			// Update URL
			const url = new URL(window.location.href);
			url.searchParams.set("modal", "connectors");
			url.searchParams.set("view", "edit");
			url.searchParams.set("connectorId", connector.id.toString());
			window.history.pushState({ modal: true }, "", url.toString());
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

				// Update URL - the effect will handle closing the modal and clearing state
				const url = new URL(window.location.href);
				url.searchParams.delete("modal");
				url.searchParams.delete("tab");
				url.searchParams.delete("view");
				url.searchParams.delete("connectorId");
				router.replace(url.pathname + url.search, { scroll: false });

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
			getFrequencyLabel,
			router,
			connectorConfig,
			connectorName,
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

				// Update URL - for MCP from list view, go back to list; otherwise close modal
				const url = new URL(window.location.href);
				if (editingConnector.connector_type === "MCP_CONNECTOR" && cameFromMCPList) {
					// Go back to MCP list view only if we came from there
					setViewingMCPList(true);
					url.searchParams.set("modal", "connectors");
					url.searchParams.set("view", "mcp-list");
					url.searchParams.delete("connectorId");
				} else {
					// Close modal for all other cases
					url.searchParams.delete("modal");
					url.searchParams.delete("tab");
					url.searchParams.delete("view");
					url.searchParams.delete("connectorId");
				}
				router.replace(url.pathname + url.search, { scroll: false });

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
		[editingConnector, searchSpaceId, deleteConnector, router, cameFromMCPList]
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
				toast.success("Indexing started", {
					description: "You can continue working while we sync your data.",
				});

				// Invalidate queries to refresh data
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
				});
				// Note: Don't call stopIndexing here - let useIndexingConnectors hook
				// detect when last_indexed_at changes via Electric SQL
			} catch (error) {
				console.error("Error indexing connector content:", error);
				toast.error(error instanceof Error ? error.message : "Failed to start indexing");
				// Stop indexing state on error
				if (stopIndexing) {
					stopIndexing(connectorId);
				}
			}
		},
		[searchSpaceId, indexConnector, queryClient]
	);

	// Handle going back from edit view
	const handleBackFromEdit = useCallback(() => {
		// If editing an MCP connector and came from MCP list, go back to MCP list view
		if (editingConnector?.connector_type === "MCP_CONNECTOR" && cameFromMCPList) {
			setViewingMCPList(true);
			setCameFromMCPList(false);
			const url = new URL(window.location.href);
			url.searchParams.set("modal", "connectors");
			url.searchParams.set("view", "mcp-list");
			url.searchParams.delete("connectorId");
			router.replace(url.pathname + url.search, { scroll: false });
			setEditingConnector(null);
			setConnectorName(null);
			setConnectorConfig(null);
			return;
		}

		// If we came from accounts list view, go back there
		if (cameFromAccountsList && editingConnector) {
			// Restore accounts list view
			setViewingAccountsType(cameFromAccountsList);
			setCameFromAccountsList(null);
			const url = new URL(window.location.href);
			url.searchParams.set("modal", "connectors");
			url.searchParams.set("view", "accounts");
			url.searchParams.set("connectorType", cameFromAccountsList.connectorType);
			url.searchParams.delete("connectorId");
			router.replace(url.pathname + url.search, { scroll: false });
		} else {
			// Otherwise, go back to main connector popup (preserve the tab the user was on)
			const url = new URL(window.location.href);
			url.searchParams.set("modal", "connectors");
			url.searchParams.set("tab", activeTab); // Use current tab instead of always "all"
			url.searchParams.delete("view");
			url.searchParams.delete("connectorId");
			router.replace(url.pathname + url.search, { scroll: false });
		}
		setEditingConnector(null);
		setConnectorName(null);
		setConnectorConfig(null);
	}, [router, cameFromAccountsList, editingConnector, cameFromMCPList, activeTab]);

	// Handle dialog open/close
	const handleOpenChange = useCallback(
		(open: boolean) => {
			setIsOpen(open);

			if (open) {
				const url = new URL(window.location.href);
				url.searchParams.set("modal", "connectors");
				url.searchParams.set("tab", activeTab);
				window.history.pushState({ modal: true }, "", url.toString());
			} else {
				const url = new URL(window.location.href);
				url.searchParams.delete("modal");
				url.searchParams.delete("tab");
				url.searchParams.delete("success");
				url.searchParams.delete("connector");
				url.searchParams.delete("view");
				window.history.pushState({ modal: false }, "", url.toString());
				setIsScrolled(false);
				setSearchQuery("");
				if (!isStartingIndexing && !isSaving && !isDisconnecting && !isCreatingConnector) {
					setIndexingConfig(null);
					setIndexingConnector(null);
					setIndexingConnectorConfig(null);
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
					setConnectingConnectorType(null);
					setViewingAccountsType(null);
					setCameFromAccountsList(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
				}
			}
		},
		[activeTab, isStartingIndexing, isDisconnecting, isSaving, isCreatingConnector]
	);

	// Handle tab change
	const handleTabChange = useCallback((value: string) => {
		setActiveTab(value);
		const url = new URL(window.location.href);
		url.searchParams.set("tab", value);
		window.history.replaceState({ modal: true }, "", url.toString());
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
		searchSpaceId,
		allConnectors,
		viewingAccountsType,
		viewingMCPList,

		// Setters
		setSearchQuery,
		setStartDate,
		setEndDate,
		setPeriodicEnabled,
		setFrequencyMinutes,
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
